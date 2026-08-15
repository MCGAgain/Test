from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .io import read_spectrum
from .library import STANDARD_EXPECTED_LINES
from .models import Calibration, Spectrum
from .preprocess import smooth_counts


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
