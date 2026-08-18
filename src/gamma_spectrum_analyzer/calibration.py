from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .io import read_spectrum
from .library import AUTO_CALIBRATION_LINES, STANDARD_EXPECTED_LINES
from .models import Calibration, Spectrum
from .peaks import find_and_fit_peaks
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


def auto_energy_calibration(
    spectrum: Spectrum,
    lines: list[tuple[float, float, str]] | None = None,
    prominence_sigma: float = 3.0,
    distance: int = 8,
    max_peaks: int = 120,
) -> Calibration:
    """Derive a per-spectrum energy calibration from the data itself.

    Different batches of spectra were measured on different detector gains
    (e.g. the identification test samples use ~0.2796 keV/channel while the
    standard sources and the Ra/Th/K samples use ~0.297 keV/channel), so one
    global calibration is wrong for a mixed set.  This builds a robust
    RANSAC-style calibration:

    1. find peaks with a provisional gain,
    2. match every peak against :data:`AUTO_CALIBRATION_LINES` to get candidate
       gains ``E/ch``,
    3. cluster the gains (correct matches pile up at the true gain, wrong
       matches scatter),
    4. fit a low-degree polynomial through the inlier ``(channel, energy)``
       pairs.
    """
    if lines is None:
        lines = AUTO_CALIBRATION_LINES
    provisional = Calibration([0.0, 0.3, 0.0])
    peaks = find_and_fit_peaks(
        spectrum, provisional, prominence_sigma=prominence_sigma,
        distance=distance, max_peaks=max_peaks,
    )

    peak_channels = np.asarray([float(p.channel) for p in peaks if p.channel > 0], dtype=float)
    peak_weights = np.asarray([max(float(p.net_area), 1.0) for p in peaks if p.channel > 0], dtype=float)
    if len(peak_channels) < 3:
        raise RuntimeError("Not enough peaks to auto-calibrate the spectrum.")
    line_energies = np.asarray([line[0] for line in lines], dtype=float)

    a0, gain = _robust_calibration(peak_channels, peak_weights, line_energies)
    inlier_pairs = _select_inliers(peaks, lines, a0, gain, tolerance=3.0)
    if len(inlier_pairs) < 3:
        raise RuntimeError("Could not find a consistent energy calibration.")

    pairs = sorted(inlier_pairs, key=lambda t: t[0])
    xs = np.asarray([p[0] for p in pairs], dtype=float)
    ys = np.asarray([p[1] for p in pairs], dtype=float)
    ws = np.asarray([p[2] for p in pairs], dtype=float)
    use_quadratic = len(pairs) >= 4 and xs.max() - xs.min() > 500
    if use_quadratic:
        a2, a1, a0 = map(float, np.polyfit(xs, ys, 2, w=ws))
        # HPGe curvature is tiny (~1e-8 keV/ch^2); a large |a2| means the
        # quadratic is over-fitting low-channel peak-centroid noise.  Reject it
        # (fall back to linear) if it bends the calibration by >15 keV at the
        # highest inlier channel.
        if abs(a2) * xs.max() ** 2 > 15.0:
            use_quadratic = False
    if not use_quadratic:
        a1, a0 = map(float, np.polyfit(xs, ys, 1, w=ws))
        a2 = 0.0
    return Calibration([a0, a1, a2])


def _robust_calibration(
    peak_channels: np.ndarray,
    peak_weights: np.ndarray,
    line_energies: np.ndarray,
) -> tuple[float, float]:
    """Find (a0, gain) by combining three complementary lines of evidence.

    A single estimator is not enough: the test samples use ~0.2796 keV/channel
    while the standard sources and Ra/Th/K samples use ~0.297 keV/channel, and
    every spectrum contains one dominant peak (Cs-137) that a wrong gain can
    tie to a different line.  We therefore build a small candidate pool, score
    every candidate by how many strong peaks land on library lines after the
    offset is removed, and let two independent priors break the ties:

    1. anchored aggregation  - for each strong peak x line ratio ``g = E/ch``,
       count partners consistent with the a0-free difference formula
       ``E_b = E_a + g*(ch_b - ch_a)``.  True multi-line nuclides pile up at
       the true gain, accidental ratios scatter.
    2. a0-consistent scoring - for every candidate, recover a0 as the weighted
       median residual of peaks near a library line, then score the log2 weight
       of peaks within tolerance, boosted by how wide the matched lines span.
    3. dominant-peak anchor  - the strongest peaks of a real spectrum are real
       gamma lines, so gains that place a top-3 peak exactly on a library line
       are strong hypotheses.  A candidate that matches no top-3 peak is
       discarded unless nothing else survives.
    """
    weights = np.asarray(peak_weights, dtype=float)
    channels = np.asarray(peak_channels, dtype=float)
    log_w = np.log2(np.maximum(weights, 1.0))

    g_min, g_max, g_step = 0.15, 0.40, 0.0005
    tol = 3.0  # keV
    n_bins = int(np.ceil((g_max - g_min) / g_step))

    # --- 1. anchored aggregation candidates (top-4 histogram bins) ---
    strong = np.argsort(weights)[::-1][:40]
    strong.sort()
    agg_ch = channels[strong]
    agg_log = log_w[strong]
    anchors = np.argsort(agg_log)[::-1][:15]
    hist = np.zeros(n_bins, dtype=np.float64)
    for a in anchors:
        ch_a = agg_ch[a]
        la = agg_log[a]
        for e_a in line_energies:
            g = e_a / ch_a
            if not (g_min < g < g_max):
                continue
            s = la
            for b in range(len(agg_ch)):
                if b == a:
                    continue
                e_b_pred = e_a + g * (agg_ch[b] - ch_a)
                if np.abs(line_energies - e_b_pred).min() <= tol:
                    s += agg_log[b]
            hist[int((g - g_min) / g_step)] += s
    top_bins = np.argsort(hist)[::-1][:4]
    candidates = [g_min + g_step * (i + 0.5) for i in top_bins if hist[i] > 0]

    # --- 2. a0-consistent residual-count candidates (top-3) ---
    strong60 = np.argsort(weights)[::-1][:60]
    strong60.sort()
    sc60 = channels[strong60]
    sl60 = log_w[strong60]
    resid_top: list[tuple[float, float]] = []
    for g in np.arange(g_min, g_max, g_step):
        score, _a0 = _a0_consistent_score(sc60, sl60, line_energies, g, tol)
        if score > 0:
            resid_top.append((score, g))
    resid_top.sort(reverse=True)
    candidates += [g for _score, g in resid_top[:3]]

    # --- 3. dominant-peak anchors (top-3 peaks are real lines) ---
    peak_order = np.argsort(weights)[::-1]
    for j in range(min(3, len(peak_order))):
        ch0 = channels[peak_order[j]]
        for e in line_energies:
            g = e / ch0
            if g_min < g < g_max:
                candidates.append(g)

    # Deduplicate (gain bins closer than 3 bins are the same hypothesis).
    unique: list[float] = []
    for g in candidates:
        if not any(abs(g - u) < 0.003 for u in unique):
            unique.append(g)

    # --- score every candidate ---
    scored: list[tuple[float, int, float, float]] = []
    for g in unique:
        score, a0 = _a0_consistent_score(sc60, sl60, line_energies, g, tol)
        if score <= 0:
            continue
        span = _matched_energy_span(sc60, sl60, line_energies, g, a0, tol)
        dom = 0
        for j in range(min(3, len(peak_order))):
            pred = channels[peak_order[j]] * g
            nearest = line_energies[np.argmin(np.abs(line_energies - pred))]
            if abs(nearest - pred) <= tol:
                dom += 1
        # Wide energy span of the matched lines is a strong sign of a real
        # calibration, but it must not outweigh the inlier weight itself.
        scored.append((score * (0.5 + span / 2500.0), dom, a0, g))

    if not scored:
        raise RuntimeError("Could not find a consistent energy calibration.")

    scored.sort(reverse=True)
    with_dom = [x for x in scored if x[1] >= 1]
    _val, _dom, a0, gain = with_dom[0] if with_dom else scored[0]
    return float(a0), float(gain)


def _a0_consistent_score(
    sc: np.ndarray,
    sl: np.ndarray,
    line_energies: np.ndarray,
    g: float,
    tol: float,
) -> tuple[float, float]:
    """Score a candidate gain: a0 is the weighted-median residual of peaks that
    come within 8 keV of a library line, and the score is the summed log2
    weight of peaks whose residual is within ``tol`` of a0."""
    pred = g * sc
    d_energy = np.abs(pred[:, None] - line_energies[None, :])
    nearest = d_energy.min(axis=1)
    nearest_line = line_energies[d_energy.argmin(axis=1)]
    ok = nearest <= 8.0
    if ok.sum() == 0:
        return 0.0, 0.0
    residuals = nearest_line[ok] - pred[ok]
    w = sl[ok]
    order = np.argsort(residuals)
    residuals = residuals[order]
    w = w[order]
    cumulative = np.cumsum(w)
    a0 = residuals[int(np.searchsorted(cumulative, cumulative[-1] / 2.0))]
    matched = np.abs(nearest_line - pred - a0) <= tol
    return float(sl[matched].sum()), float(a0)


def _matched_energy_span(
    sc: np.ndarray,
    sl: np.ndarray,
    line_energies: np.ndarray,
    g: float,
    a0: float,
    tol: float,
) -> float:
    """Energy span (keV) covered by the distinct lines matched under (a0, g)."""
    pred = g * sc
    d_energy = np.abs(pred[:, None] - line_energies[None, :])
    nearest_line = line_energies[d_energy.argmin(axis=1)]
    matched = np.abs(nearest_line - pred - a0) <= tol
    if matched.sum() == 0:
        return 0.0
    energies = np.unique(nearest_line[matched])
    return float(energies[-1] - energies[0])


def _select_inliers(
    peaks: list,
    lines: list[tuple[float, float, str]],
    a0: float,
    gain: float,
    tolerance: float = 3.0,
) -> list[tuple[float, float, float]]:
    """Return (channel, energy, weight) pairs for peaks whose closest library
    line falls within ``tolerance`` keV of the calibration prediction."""
    inlier_pairs: list[tuple[float, float, float]] = []
    for peak in peaks:
        ch = float(peak.channel)
        if ch <= 0:
            continue
        predicted = a0 + gain * ch
        energy, _yield, _label = min(lines, key=lambda line: abs(line[0] - predicted))
        if abs(energy - predicted) <= tolerance:
            inlier_pairs.append((ch, energy, max(float(peak.net_area), 1.0)))
    return inlier_pairs


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
