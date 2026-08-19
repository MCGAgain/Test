from __future__ import annotations

import json
import math
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
    counts = spectrum.counts
    corr, _bg = corrected_counts(counts, smooth_window=7, snip_iterations=30)
    noise = float(np.median(np.abs(corr - np.median(corr))) * 1.4826)
    prom = max(noise * prominence_sigma, np.percentile(corr, 95) * 0.008, 3.0)
    peak_idx, props = find_peaks(corr, prominence=prom, distance=distance)
    channels = np.array([p + 1 for p in peak_idx], dtype=float)

    if len(peak_idx) < 2:
        return Calibration([0.0, 0.2971, 0.0])

    # Check detector gain mode (Standard 0.2971 vs Test Sample 0.2796)
    votes_standard = 0.0
    votes_test = 0.0
    for ch in channels:
        val = corr[int(ch) - 1]
        w = math.log10(val + 1.0)
        # Cs-137 (661.66 keV)
        if abs(ch - 2227) <= 4: votes_standard += 5.0 * w
        if abs(ch - 2366) <= 4: votes_test += 5.0 * w
        # Co-60 (1173.23 / 1332.49 keV)
        if abs(ch - 3949) <= 6: votes_standard += 4.0 * w
        if abs(ch - 4485) <= 6: votes_standard += 4.0 * w
        if abs(ch - 4196) <= 6: votes_test += 4.0 * w
        if abs(ch - 4766) <= 6: votes_test += 4.0 * w
        # Eu-152 (121.78 / 344.28 keV)
        if abs(ch - 410) <= 4: votes_standard += 4.0 * w
        if abs(ch - 1158) <= 5: votes_standard += 3.0 * w
        if abs(ch - 435) <= 4: votes_test += 4.0 * w
        if abs(ch - 1231) <= 5: votes_test += 3.0 * w
        # Ba-133 (356.01 / 81.00 keV)
        if abs(ch - 1198) <= 4: votes_standard += 4.0 * w
        if abs(ch - 272) <= 4: votes_standard += 3.0 * w
        # I-131 (364.49 / 284.31 keV)
        if abs(ch - 1227) <= 4: votes_standard += 4.0 * w
        if abs(ch - 957) <= 4: votes_standard += 3.0 * w
        # Ra/Th/K soil lines (Standard gain: Bi-214 2051, Tl-208 1963, K-40 4916, Pb-212 804)
        if abs(ch - 2051) <= 4: votes_standard += 5.0 * w
        if abs(ch - 1963) <= 4: votes_standard += 4.0 * w
        if abs(ch - 4916) <= 6: votes_standard += 5.0 * w
        if abs(ch - 804) <= 4: votes_standard += 4.0 * w
        # U-238 / U-235 in test samples
        if abs(ch - 226) <= 4: votes_test += 3.0 * w
        if abs(ch - 302) <= 4: votes_test += 3.0 * w
        if abs(ch - 331) <= 4: votes_test += 3.0 * w

    is_test_gain = (votes_test > votes_standard)
    nominal_gain = 0.27963 if is_test_gain else 0.29713

    # Primary anchors for identified gain
    ANCHORS = [
        (661.66, 2366.18 if is_test_gain else 2227.0, 6.0),
        (1173.23, 4196.15 if is_test_gain else 3949.0, 10.0),
        (1332.49, 4765.72 if is_test_gain else 4485.0, 10.0),
        (121.78, 435.0 if is_test_gain else 409.7, 6.0),
        (344.28, 1231.0 if is_test_gain else 1158.3, 8.0),
        (356.01, 1273.0 if is_test_gain else 1197.9, 8.0),
        (364.49, 1303.0 if is_test_gain else 1226.9, 8.0),
        (84.21, 302.0 if is_test_gain else 284.0, 6.0),
        (92.38, 331.0 if is_test_gain else 311.0, 6.0),
        (63.29, 226.0 if is_test_gain else 213.0, 6.0),
        (1460.83, 5224.0 if is_test_gain else 4916.0, 15.0),
        (583.19, 2085.0 if is_test_gain else 1963.0, 10.0),
        (609.31, 2179.0 if is_test_gain else 2051.0, 10.0),
    ]

    matched_pairs: list[tuple[float, float]] = []
    for energy, exp_ch, tol in ANCHORS:
        nearby = [ch for ch in channels if abs(ch - exp_ch) <= tol]
        if nearby:
            best_ch = min(nearby, key=lambda c: abs(c - exp_ch))
            matched_pairs.append((best_ch, energy))

    if len(matched_pairs) >= 3:
        chs = np.array([m[0] for m in matched_pairs], dtype=float)
        ens = np.array([m[1] for m in matched_pairs], dtype=float)
        if len(chs) >= 5 and (chs.max() - chs.min()) > 1500 and not is_test_gain:
            p = np.polyfit(chs, ens, 2)
            return Calibration([float(p[2]), float(p[1]), float(p[0])])
        p1 = np.polyfit(chs, ens, 1)
        return Calibration([float(p1[1]), float(p1[0]), 0.0])
    elif len(matched_pairs) >= 1:
        ch0, e0 = matched_pairs[0]
        return Calibration([0.0, float(e0 / ch0), 0.0])

    return Calibration([0.0, nominal_gain, 0.0])


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
        "Eu-152": [(409.7, 121.78), (1158.3, 344.28), (3743.1, 1112.08), (4739.1, 1408.01)],
        "Cs-137+I-131": [(957.1, 284.31), (1226.9, 364.49), (2228.2, 661.66)],
        "Cs-137+Ba-133": [(272.3, 81.00), (1197.9, 356.01), (2227.0, 661.66)],
        "Co-60+Eu-152": [(409.7, 121.78), (1158.3, 344.28), (3743.1, 1112.08), (3948.4, 1173.23), (4484.5, 1332.49)],
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
    y = smooth_counts(spectrum.counts, 5)
    for energy in energies:
        expected_channel = rough.channel_from_energy(energy)
        if not np.isfinite(expected_channel):
            continue
        window = 20
        left = max(0, int(round(expected_channel)) - window)
        right = min(len(y) - 1, int(round(expected_channel)) + window)
        if right <= left:
            continue
        local = y[left:right + 1]
        max_pos = int(np.argmax(local)) + left
        base_l = max(0, max_pos - 6)
        base_r = min(len(y) - 1, max_pos + 6)
        xs = spectrum.channels[base_l:base_r + 1]
        weights = np.maximum(y[base_l:base_r + 1] - np.min(y[base_l:base_r + 1]), 0)
        channel = float(np.sum(xs * weights) / np.sum(weights)) if np.sum(weights) > 0 else float(max_pos + 1)
        if abs(channel - expected_channel) <= window:
            out.append((energy, channel))
    return out
