from __future__ import annotations

import math
from collections import defaultdict

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
