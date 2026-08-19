from __future__ import annotations

import math

import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks, peak_widths

from .models import Calibration, Peak, Spectrum
from .preprocess import corrected_counts


def find_and_fit_peaks(
    spectrum: Spectrum,
    calibration: Calibration | None = None,
    prominence_sigma: float = 3.0,
    distance: int = 8,
    smooth_window: int = 7,
    snip_iterations: int = 18,
    max_peaks: int = 150,
) -> list[Peak]:
    corrected, background = corrected_counts(spectrum.counts, smooth_window, snip_iterations)
    noise = _robust_sigma(corrected)
    prominence = max(noise * prominence_sigma, np.percentile(corrected, 95) * 0.005, 3.0)
    peak_idx, props = find_peaks(corrected, prominence=prominence, distance=distance)
    if len(peak_idx) == 0:
        return []
    if len(peak_idx) > max_peaks:
        strongest = np.argsort(props["prominences"])[-max_peaks:]
        peak_idx = peak_idx[strongest]
        order = np.argsort(peak_idx)
        peak_idx = peak_idx[order]

    widths = peak_widths(corrected, peak_idx, rel_height=0.5)
    result: list[Peak] = []
    for j, idx in enumerate(peak_idx):
        approx_fwhm = max(float(widths[0][j]), 2.5)
        half_window = int(max(6, min(30, approx_fwhm * 3.0)))
        left = max(0, int(idx) - half_window)
        right = min(len(spectrum.counts) - 1, int(idx) + half_window)
        peak = _fit_one_peak(spectrum, corrected, idx, approx_fwhm, left, right, calibration)
        if peak.net_area > 0:
            result.append(peak)
    return sorted(result, key=lambda p: p.channel)


def _fit_one_peak(
    spectrum: Spectrum,
    corrected: np.ndarray,
    idx: int,
    approx_fwhm: float,
    left: int,
    right: int,
    calibration: Calibration | None,
) -> Peak:
    x = spectrum.channels[left:right + 1]
    y = spectrum.counts[left:right + 1]
    b0 = float(np.median(np.r_[y[: max(2, len(y) // 6)], y[-max(2, len(y) // 6):]]))
    amp0 = max(float(spectrum.counts[idx] - b0), 1.0)
    sigma0 = max(approx_fwhm / 2.355, 1.0)
    center0 = float(spectrum.channels[idx])

    try:
        popt, pcov = curve_fit(
            _gaussian_linear,
            x,
            y,
            p0=[amp0, center0, sigma0, b0, 0.0],
            bounds=([0, x[0], 0.3, 0, -np.inf], [np.inf, x[-1], 25.0, np.inf, np.inf]),
            maxfev=300,
        )
        amp, center, sigma, base, slope = map(float, popt)
    except Exception:
        amp, center, sigma, base, slope = amp0, center0, sigma0, b0, 0.0

    fwhm_ch = 2.354820045 * abs(sigma)
    fwtm_ch = 4.29193426 * abs(sigma)
    roi_l = max(1, int(round(center - 1.60 * fwhm_ch)))
    roi_r = min(len(spectrum.counts), int(round(center + 1.60 * fwhm_ch)))
    if roi_r <= roi_l:
        roi_l = max(1, int(round(center - 2)))
        roi_r = min(len(spectrum.counts), int(round(center + 2)))

    idx_l = roi_l - 1
    idx_r = roi_r - 1
    roi_corr = corrected[idx_l:idx_r + 1]
    roi_area = float(np.sum(roi_corr))

    roi_raw = spectrum.counts[idx_l:idx_r + 1]
    n_roi = len(roi_raw)
    bgl = float(roi_raw[0]) if n_roi > 0 else 0.0
    bgr = float(roi_raw[-1]) if n_roi > 0 else 0.0
    bg_area = (bgl + bgr) * n_roi / 2.0
    trap_net = max(float(np.sum(roi_raw)) - bg_area, 0.0)
    gauss_area = float(abs(amp * sigma * math.sqrt(2 * math.pi)))
    net_area = trap_net if (trap_net > 0 and abs(trap_net - gauss_area) < gauss_area * 0.45) else gauss_area
    if roi_area < net_area:
        roi_area = net_area

    g_raw = float(np.sum(roi_raw))
    var = g_raw + (float(n_roi) / 2.0) ** 2 * (bgl + bgr)
    area_uncert = 100.0 * math.sqrt(max(var, 1.0)) / max(net_area, 1.0)

    energy = float(calibration.energy(center)) if calibration else None
    fwhm_kev = None
    fwtm_kev = None
    if calibration and energy is not None:
        gain = float(calibration.energy(center + 0.5) - calibration.energy(center - 0.5))
        fwhm_kev = fwhm_ch * abs(gain)
        fwtm_kev = fwtm_ch * abs(gain)

    count_rate = None
    if spectrum.live_time and spectrum.live_time > 0:
        count_rate = roi_area / spectrum.live_time

    return Peak(
        channel=center,
        roi_l=roi_l,
        roi_r=roi_r,
        energy_kev=energy,
        fwhm_channel=fwhm_ch,
        fwhm_kev=fwhm_kev,
        fwtm_channel=fwtm_ch,
        fwtm_kev=fwtm_kev,
        roi_area=roi_area,
        net_area=net_area,
        area_uncert_percent=area_uncert,
        count_rate=count_rate,
    )


def _gaussian_linear(x: np.ndarray, amp: float, center: float, sigma: float, base: float, slope: float) -> np.ndarray:
    return amp * np.exp(-0.5 * ((x - center) / sigma) ** 2) + base + slope * (x - center)


def _robust_sigma(y: np.ndarray) -> float:
    med = np.median(y)
    mad = np.median(np.abs(y - med))
    return float(max(1.4826 * mad, 1.0))
