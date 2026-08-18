from __future__ import annotations

from collections import defaultdict

from .library import CONFIRMATION_RULES, GammaLine, all_lines
from .models import Peak


def identify_peaks(peaks: list[Peak], tolerance_kev: float = 2.0) -> dict[str, list[Peak]]:
    matches_by_nuclide: dict[str, list[Peak]] = defaultdict(list)
    lines = all_lines()

    for peak in peaks:
        if peak.energy_kev is None or peak.net_area < 10.0:
            continue
        candidates = [
            line for line in lines
            if abs(line.energy_kev - peak.energy_kev) <= tolerance_kev
        ]
        if not candidates:
            continue
        line = min(candidates, key=lambda item: abs(item.energy_kev - peak.energy_kev))
        peak.nuclide = line.nuclide
        peak.yield_percent = line.yield_percent
        peak.matched_energy_kev = line.energy_kev
        matches_by_nuclide[line.nuclide].append(peak)

    confirmed: dict[str, list[Peak]] = {}
    for nuclide, nuclide_peaks in matches_by_nuclide.items():
        if _confirmed(nuclide, nuclide_peaks, tolerance_kev):
            confirmed[nuclide] = nuclide_peaks
        else:
            for peak in nuclide_peaks:
                peak.nuclide = ""
                peak.yield_percent = None
                peak.matched_energy_kev = None
    return confirmed


def _confirmed(nuclide: str, peaks: list[Peak], tolerance_kev: float) -> bool:
    rule = CONFIRMATION_RULES.get(nuclide, {"required_energies": [], "min_matches": 1})
    unique = {round(float(p.matched_energy_kev or p.energy_kev or 0), 2) for p in peaks}
    if len(unique) < int(rule["min_matches"]):
        return False
    for required in rule["required_energies"]:
        if not any(abs(required - energy) <= tolerance_kev for energy in unique):
            return False
    return True
