from __future__ import annotations

import math
from collections import defaultdict

from .efficiency import EfficiencyCurve
from .models import Calibration, Peak, Spectrum


def fill_quantification(peaks: list[Peak], spectrum: Spectrum, calibration: Calibration) -> dict[str, dict[str, float]]:
    for peak in peaks:
        if not peak.energy_kev or not peak.yield_percent:
            continue
        peak.efficiency = calibration.efficiency(peak.energy_kev)
        if not peak.efficiency or not spectrum.live_time or spectrum.live_time <= 0:
            continue
        denom = spectrum.live_time * peak.efficiency * (peak.yield_percent / 100.0)
        if denom <= 0:
            continue
        peak.activity_bq = peak.net_area / denom
        peak.activity_uncert_percent = peak.area_uncert_percent

    by_nuclide: dict[str, list[Peak]] = defaultdict(list)
    for peak in peaks:
        if peak.nuclide and not peak.nuclide.endswith("?") and peak.activity_bq:
            by_nuclide[peak.nuclide].append(peak)

    summary: dict[str, dict[str, float]] = {}
    for nuclide, items in by_nuclide.items():
        weights = []
        values = []
        for peak in items:
            sigma = peak.activity_bq * (peak.activity_uncert_percent or 100.0) / 100.0
            if sigma > 0:
                weights.append(1.0 / (sigma * sigma))
                values.append(peak.activity_bq)
        if weights:
            total_w = sum(weights)
            mean = sum(v * w for v, w in zip(values, weights)) / total_w
            uncert = math.sqrt(1.0 / total_w)
            summary[nuclide] = {
                "activity_bq": mean,
                "activity_uncert_percent": 100.0 * uncert / mean if mean else float("nan"),
                "lines": float(len(values)),
            }
    return summary


def quantify_specific_activity(
    peaks: list[Peak],
    live_time: float | None,
    efficiency: EfficiencyCurve,
    mass_kg: float,
    lines_by_nuclide: dict[str, list[tuple[float, float]]],
    tolerance_kev: float = 4.0,
) -> dict[str, dict[str, float]]:
    """Compute specific activities C_s (Bq/kg) following GB/T 11743-2013:

        C_s = A_s / m = N_net / (epsilon(E) * P_gamma * t_live * m)

    For each nuclide, every configured line is matched to its peak (within
    tolerance) and the per-line estimates are combined with an inverse-variance
    weighted mean.  Returns one dict per nuclide with the specific activity,
    total activity and combined uncertainty.
    """
    if not live_time or live_time <= 0:
        raise ValueError("Spectrum has no positive live time.")
    result: dict[str, dict[str, float]] = {}
    for nuclide, lines in lines_by_nuclide.items():
        values: list[float] = []
        weights: list[float] = []
        used_lines = 0
        for energy, yield_fraction in lines:
            best = min(
                (p for p in peaks if p.energy_kev is not None),
                key=lambda p: abs(p.energy_kev - energy),
                default=None,
            )
            if best is None or abs(best.energy_kev - energy) > tolerance_kev:
                continue
            eff = efficiency.efficiency_at(energy)
            if eff <= 0:
                continue
            activity = best.net_area / (eff * yield_fraction * live_time)
            specific = activity / mass_kg if mass_kg > 0 else float("nan")
            sigma = specific * (best.area_uncert_percent or 100.0) / 100.0
            if sigma > 0:
                values.append(specific)
                weights.append(1.0 / (sigma * sigma))
                used_lines += 1
        if not values:
            continue
        total_weight = sum(weights)
        mean = sum(v * w for v, w in zip(values, weights)) / total_weight
        uncert = math.sqrt(1.0 / total_weight)
        result[nuclide] = {
            "specific_activity_bq_per_kg": mean,
            "activity_bq": mean * mass_kg,
            "mass_kg": mass_kg,
            "activity_uncert_percent": 100.0 * uncert / mean if mean else float("nan"),
            "lines": used_lines,
        }
    return result
