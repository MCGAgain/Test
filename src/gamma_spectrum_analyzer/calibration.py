from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks

from .io import read_spectrum
from .library import AUTO_CALIBRATION_LINES, STANDARD_EXPECTED_LINES
from .models import Calibration, Spectrum
from .preprocess import corrected_counts, smooth_counts


def train_energy_calibration(standards_dir: str | Path) -> tuple[Calibration, list[dict[str, float | str]]]:
    standards_dir = Path(standards_dir)
    pairs: list[tuple[float, float, str]] = []

    for standard_name, energies in STANDARD_EXPECTED_LINES.items():
        files = sorted((standards_dir / standard_name).glob("*.xls"))
        if not files:
            continue
        spectrum = read_spectrum(files[0])
        rough = _rough_calibration_for_standard(standard_name)
        channels = _assign_channels(spectrum, energies, rough)
        for energy, channel in channels:
            pairs.append((channel, energy, standard_name))

    if len(pairs) < 3:
        raise RuntimeError("Need at least three standard peaks to fit quadratic energy calibration.")
    ch = np.asarray([p[0] for p in pairs], dtype=float)
    en = np.asarray([p[1] for p in pairs], dtype=float)
    coeff_desc = np.polyfit(ch, en, 2)
    a2, a1, a0 = map(float, coeff_desc)
    calibration = Calibration([a0, a1, a2])
    used = [{"channel": c, "energy_kev": e, "standard": s} for c, e, s in pairs]
    return calibration, used


# Signature pairs of gamma lines: (E1, E2)
SIGNATURE_PAIRS: list[tuple[float, float]] = [
    (1173.23, 1332.49),  # Co-60
    (121.78, 344.28),    # Eu-152
    (344.28, 1408.01),   # Eu-152
    (121.78, 1408.01),   # Eu-152
    (81.00, 356.01),     # Ba-133
    (356.01, 661.66),    # Ba-133 + Cs-137
    (364.49, 661.66),    # I-131 + Cs-137
    (63.29, 92.38),      # U-238
    (84.21, 143.76),     # U-235
    (84.21, 185.72),     # U-235
    (238.63, 583.19),    # Th-232
    (583.19, 911.20),    # Th-232
    (351.92, 609.31),    # Ra-226
    (609.31, 1764.49),   # Ra-226
    (661.66, 1173.23),   # Cs-137 + Co-60
    (661.66, 1460.83),   # Cs-137 + K-40
    (609.31, 1460.83),   # Ra-226 + K-40
]

ANCHOR_LINES: list[float] = [
    661.66, 1173.23, 1332.49, 121.78, 344.28, 356.01, 364.49,
    1460.83, 609.31, 583.19, 238.63, 185.72, 81.00, 92.38, 63.29
]


def auto_energy_calibration(
    spectrum: Spectrum,
    lines: list[tuple[float, float, str]] | list[float] | None = None,
    prominence_sigma: float = 3.0,
    distance: int = 8,
    max_peaks: int = 40,
) -> Calibration:
    """Derive a fast, robust per-spectrum energy calibration from peak morphology.

    Handles mixed detector gains (e.g. Test Samples 1-5 with ~0.2796 keV/channel vs
    Standard Sources & Soil samples with ~0.2971 keV/channel) dynamically and accurately.
    """
    if lines is None:
        ref_lines = np.array([line[0] for line in AUTO_CALIBRATION_LINES], dtype=float)
    elif len(lines) > 0 and isinstance(lines[0], (tuple, list)):
        ref_lines = np.array([line[0] for line in lines], dtype=float)
    else:
        ref_lines = np.asarray(lines, dtype=float)

    counts = spectrum.counts
    corr, _bg = corrected_counts(counts, smooth_window=7, snip_iterations=30)
    noise = float(np.median(np.abs(corr - np.median(corr))) * 1.4826)
    prom = max(noise * prominence_sigma, 4.0)
    peak_idx, props = find_peaks(corr, prominence=prom, distance=distance)

    if len(peak_idx) < 2:
        return Calibration([0.0, 0.297, 0.0])

    prominences = props["prominences"]
    order = np.argsort(prominences)[::-1]
    top_peaks = peak_idx[order[:max_peaks]]
    top_prom = prominences[order[:max_peaks]]

    candidates: list[tuple[float, float]] = []

    # 1. Signature multi-line pairs
    for i in range(min(12, len(top_peaks))):
        for j in range(i + 1, min(12, len(top_peaks))):
            ch1, ch2 = sorted([top_peaks[i], top_peaks[j]])
            d_ch = ch2 - ch1
            if d_ch < 15:
                continue
            for e1, e2 in SIGNATURE_PAIRS:
                g = (e2 - e1) / d_ch
                if 0.26 <= g <= 0.34:
                    a0 = e1 - g * ch1
                    if -2.0 <= a0 <= 2.0:
                        candidates.append((a0, g))

    # 2. General combinations of top peaks with reference lines
    for i in range(min(8, len(top_peaks))):
        for j in range(i + 1, min(8, len(top_peaks))):
            ch1, ch2 = sorted([top_peaks[i], top_peaks[j]])
            d_ch = ch2 - ch1
            if d_ch < 20:
                continue
            for la in range(len(ref_lines)):
                for lb in range(la + 1, len(ref_lines)):
                    d_e = ref_lines[lb] - ref_lines[la]
                    g = d_e / d_ch
                    if 0.26 <= g <= 0.34:
                        a0 = ref_lines[la] - g * ch1
                        if -2.0 <= a0 <= 2.0:
                            candidates.append((a0, g))

    # 3. Single strong peak anchors (assuming |a0| <= 2 keV)
    for ch in top_peaks[:6]:
        for e in ANCHOR_LINES:
            g = e / ch
            if 0.26 <= g <= 0.34:
                candidates.append((0.0, g))

    if not candidates:
        return Calibration([0.0, 0.297, 0.0])

    tol = 2.0  # keV
    best_score = -1e9
    best_poly = [0.0, 0.297, 0.0]

    for a0_cand, g_cand in candidates:
        pred_e = a0_cand + g_cand * top_peaks
        dists = np.abs(pred_e[:, None] - ref_lines[None, :])
        min_dists = dists.min(axis=1)
        matched_line_idx = dists.argmin(axis=1)
        inliers = min_dists <= tol

        n_inliers = int(np.sum(inliers))
        if n_inliers < 2:
            continue

        inlier_lines = np.unique(matched_line_idx[inliers])
        span = float(ref_lines[inlier_lines[-1]] - ref_lines[inlier_lines[0]]) if len(inlier_lines) > 1 else 0.0

        inlier_prom_ratio = float(np.sum(top_prom[inliers]) / (np.sum(top_prom) + 1e-6))
        top2_matched = sum(1.0 for k in range(min(2, len(top_peaks))) if inliers[k])

        resids = np.abs(pred_e[inliers] - ref_lines[matched_line_idx[inliers]])
        mean_resid = float(np.mean(resids))

        score = (
            np.sum(np.log2(top_prom[inliers] + 2.0))
            + 25.0 * inlier_prom_ratio
            + 6.0 * top2_matched
            - 3.0 * mean_resid
            - 1.5 * abs(a0_cand)
        ) * (1.0 + span / 500.0)

        if score > best_score:
            best_score = score
            inlier_ch = top_peaks[inliers]
            inlier_en = ref_lines[matched_line_idx[inliers]]
            w = np.log2(top_prom[inliers] + 2.0)

            if len(inlier_ch) >= 4 and (inlier_ch.max() - inlier_ch.min()) > 1000:
                p = np.polyfit(inlier_ch, inlier_en, 2, w=w)
                if abs(p[0]) * inlier_ch.max() ** 2 < 8.0:  # Avoid unphysical curvature
                    poly = [float(p[2]), float(p[1]), float(p[0])]
                else:
                    p1 = np.polyfit(inlier_ch, inlier_en, 1, w=w)
                    poly = [float(p1[1]), float(p1[0]), 0.0]
            else:
                p = np.polyfit(inlier_ch, inlier_en, 1, w=w)
                poly = [float(p[1]), float(p[0]), 0.0]
            best_poly = poly

    return Calibration(best_poly)


def save_calibration(calibration: Calibration, path: str | Path, used_peaks: list[dict] | None = None) -> None:
    payload = {
        "energy_coefficients": calibration.energy_coefficients,
        "efficiency_coefficients": calibration.efficiency_coefficients,
        "used_peaks": used_peaks or [],
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_calibration(path: str | Path) -> Calibration:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return Calibration(payload["energy_coefficients"], payload.get("efficiency_coefficients"))


def fit_efficiency_calibration(points: list[tuple[float, float]], degree: int = 2) -> list[float]:
    clean = [(e, eff) for e, eff in points if e > 0 and eff > 0]
    if len(clean) < degree + 1:
        raise ValueError("Not enough positive efficiency points.")
    x = np.log(np.asarray([p[0] for p in clean], dtype=float))
    y = np.log(np.asarray([p[1] for p in clean], dtype=float))
    return [float(v) for v in np.polyfit(x, y, degree)]


def _rough_calibration_for_standard(name: str) -> Calibration:
    anchors = {
        "Co-60": [(3949.0, 1173.23), (4485.0, 1332.49)],
        "Eu-152": [(410.0, 121.78), (1158.0, 344.28)],
        "Cs-137+I-131": [(1227.0, 364.49), (2228.0, 661.66)],
        "Cs-137+Ba-133": [(272.0, 81.00), (1198.0, 356.01), (2227.0, 661.66)],
        "Co-60+Eu-152": [(410.0, 121.78), (1158.0, 344.28), (4485.0, 1332.49)],
    }.get(name, [(0.0, 0.0), (4485.0, 1332.49)])
    ch = np.asarray([a[0] for a in anchors], dtype=float)
    en = np.asarray([a[1] for a in anchors], dtype=float)
    deg = min(2, len(anchors) - 1)
    coeff = np.polyfit(ch, en, deg)
    if deg == 1:
        a1, a0 = coeff
        return Calibration([float(a0), float(a1), 0.0])
    a2, a1, a0 = coeff
    return Calibration([float(a0), float(a1), float(a2)])


def _assign_channels(spectrum: Spectrum, energies: list[float], rough: Calibration) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    y = smooth_counts(spectrum.counts, 7)
    for energy in energies:
        expected_channel = rough.channel_from_energy(energy)
        if not np.isfinite(expected_channel):
            continue
        window = int(max(25, min(120, expected_channel * 0.04)))
        left = max(0, int(round(expected_channel)) - window)
        right = min(len(y) - 1, int(round(expected_channel)) + window)
        if right <= left:
            continue
        local = y[left:right + 1]
        max_pos = int(np.argmax(local)) + left
        base_l = max(left, max_pos - 12)
        base_r = min(right, max_pos + 12)
        xs = spectrum.channels[base_l:base_r + 1]
        weights = np.maximum(y[base_l:base_r + 1] - np.percentile(local, 30), 0)
        channel = float(np.sum(xs * weights) / np.sum(weights)) if np.sum(weights) > 0 else float(max_pos)
        if abs(channel - expected_channel) <= window:
            out.append((energy, channel))
    return out
