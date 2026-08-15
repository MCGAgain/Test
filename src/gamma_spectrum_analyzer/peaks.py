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
    prominence_sigma: float = 5.0,
    distance: int = 12,
    smooth_window: int = 7,
    snip_iterations: int = 40,
    max_peaks: int = 90,
) -> list[Peak]:
    corrected, background = corrected_counts(spectrum.counts, smooth_window, snip_iterations)
    noise = _robust_sigma(corrected)
    prominence = max(noise * prominence_sigma, np.percentile(corrected, 95) * 0.015, 5.0)
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
        approx_fwhm = max(float(widths[0][j]), 3.0)
        half_window = int(max(8, min(60, approx_fwhm * 3)))
        left = max(0, int(idx) - half_window)
        right = min(len(spectrum.counts) - 1, int(idx) + half_window)
        peak = _fit_one_peak(spectrum, corrected, background, idx, left, right, calibration)
        if peak.net_area > 0:
            result.append(peak)
    return sorted(result, key=lambda p: p.channel)


def _fit_one_peak(
    spectrum: Spectrum,
    corrected: np.ndarray,
    background: np.ndarray,
    idx: int,
    left: int,
    right: int,
    calibration: Calibration | None,
) -> Peak:
    x = spectrum.channels[left:right + 1]
    y = spectrum.counts[left:right + 1]
    b0 = float(np.median(np.r_[y[: max(2, len(y) // 6)], y[-max(2, len(y) // 6):]]))
    amp0 = max(float(spectrum.counts[idx] - b0), 1.0)
    sigma0 = 3.0

    try:
        popt, pcov = curve_fit(
            _gaussian_linear,
            x,
            y,
            p0=[amp0, float(spectrum.channels[idx]), sigma0, b0, 0.0],
            bounds=([0, x[0], 0.4, 0, -np.inf], [np.inf, x[-1], 80.0, np.inf, np.inf]),
            maxfev=10000,
        )
        amp, center, sigma, base, slope = map(float, popt)
        center_unc = math.sqrt(abs(float(pcov[1, 1]))) if pcov.size else 0.0
    except Exception:
        amp, center, sigma, base, slope = amp0, float(spectrum.channels[idx]), sigma0, b0, 0.0
        center_unc = 0.0

    fwhm_ch = 2.354820045 * abs(sigma)
    roi_l = max(0, int(round(center - 2.5 * fwhm_ch)))
    roi_r = min(len(spectrum.counts) - 1, int(round(center + 2.5 * fwhm_ch)))
    roi_y = spectrum.counts[roi_l:roi_r + 1]
    roi_x = spectrum.channels[roi_l:roi_r + 1]
    local_bg = base + slope * (roi_x - center)
    roi_area = float(np.sum(roi_y))
    gaussian_area = float(abs(amp * sigma * math.sqrt(2 * math.pi)))
    bg_sub_area = float(np.sum(np.maximum(roi_y - local_bg, 0)))
    net_area = gaussian_area if np.isfinite(gaussian_area) and gaussian_area > 0 else bg_sub_area
    area_uncert = 100.0 * math.sqrt(max(roi_area, 1.0)) / max(net_area, 1.0)

    energy = float(calibration.energy(center)) if calibration else None
    fwhm_kev = None
    if calibration and energy is not None:
        e_l = float(calibration.energy(center - fwhm_ch / 2))
        e_r = float(calibration.energy(center + fwhm_ch / 2))
        fwhm_kev = abs(e_r - e_l)

    count_rate = None
    if spectrum.live_time and spectrum.live_time > 0:
        count_rate = net_area / spectrum.live_time

    return Peak(
        channel=center,
        roi_l=roi_l,
        roi_r=roi_r,
        energy_kev=energy,
        fwhm_channel=fwhm_ch,
        fwhm_kev=fwhm_kev,
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
