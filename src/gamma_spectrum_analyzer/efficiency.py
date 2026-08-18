from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from .models import Spectrum
from .peaks import find_and_fit_peaks


@dataclass
class EfficiencyPoint:
    """One measured efficiency point: net_area / (A_decay * P_gamma * t_live)."""

    energy_kev: float
    efficiency: float
    parent: str = ""
    yield_fraction: float | None = None
    excluded: bool = False


@dataclass
class CalibrationSource:
    """Certified multi-nuclide calibration source (e.g. the 7NTR-1024 soil
    efficiency source).  Activities are given at a reference date and decay
    corrected to each measurement's DATE before building the efficiency curve.
    """

    name: str
    reference_date: str                 # ISO date, e.g. "2015-01-25"
    mass_kg: float
    activities_bq: dict[str, float]
    half_lives_years: dict[str, float]
    lines: list[dict[str, float | str]]  # {"parent","energy_kev","yield"}
    excluded_energies: list[float] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str | Path) -> CalibrationSource:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=payload["name"],
            reference_date=payload["reference_date"],
            mass_kg=float(payload["mass_kg"]),
            activities_bq={k: float(v) for k, v in payload["activities_bq"].items()},
            half_lives_years={k: float(v) for k, v in payload["half_lives_years"].items()},
            lines=list(payload["lines"]),
            excluded_energies=[float(e) for e in payload.get("excluded_energies", [])],
        )


class EfficiencyCurve:
    """Piecewise log-log linear interpolation of measured efficiency points.

    A global log-log polynomial is a poor model here: the 7NTR-1024 source's
    soil matrix self-absorbs the low-energy U lines and the natural K-40 in the
    soil makes the 1460.8 keV point artificially high, while the Tl-208
    583.19 keV point sits low because the 11-year-old Th-232 chain is not yet
    in full secular equilibrium.  Piecewise interpolation through the reliable
    measured points reproduces the reference Ra/Th/K activities to ~3 % mean
    error, so each point is used exactly at its own energy.
    """

    def __init__(self, points: list[EfficiencyPoint]) -> None:
        used = sorted((p for p in points if not p.excluded), key=lambda p: p.energy_kev)
        if len(used) < 2:
            raise ValueError("Need at least two usable efficiency points.")
        self.points = points
        self.used = used
        self._xe = np.log(np.asarray([p.energy_kev for p in used], dtype=float))
        self._ye = np.log(np.asarray([p.efficiency for p in used], dtype=float))

    def efficiency_at(self, energy_kev: float) -> float:
        le = np.log(float(energy_kev))
        if le <= self._xe[0]:
            return float(np.exp(self._ye[0]))
        if le >= self._xe[-1]:
            return float(np.exp(self._ye[-1]))
        return float(np.exp(np.interp(le, self._xe, self._ye)))

    def __call__(self, energy_kev: float) -> float:
        return self.efficiency_at(energy_kev)


def decay_correct(activity_bq: float, half_life_years: float, reference_date: date, measurement_date: date) -> float:
    """Decay a certified activity from the reference date to the measurement date."""
    days = (measurement_date - reference_date).days
    return activity_bq * 0.5 ** (days / 365.25 / half_life_years)


def fit_efficiency_points(
    spectrum: Spectrum,
    source: CalibrationSource,
    calibration,
    prominence_sigma: float = 3.0,
    distance: int = 8,
    max_peaks: int = 200,
    tolerance_kev: float = 4.0,
    min_net_area: float = 100.0,
) -> list[EfficiencyPoint]:
    """Measure the calibration source spectrum and return one efficiency point
    per certified line (weak/absent lines are skipped, configured anomalous
    lines are flagged as excluded)."""
    measurement_date = date.fromisoformat(spectrum.metadata.get("DATE", source.reference_date))
    reference_date = date.fromisoformat(source.reference_date)
    if not spectrum.live_time or spectrum.live_time <= 0:
        raise ValueError("Calibration spectrum has no positive live time.")
    activities = {
        k: decay_correct(v, source.half_lives_years[k], reference_date, measurement_date)
        for k, v in source.activities_bq.items()
    }

    peaks = find_and_fit_peaks(
        spectrum, calibration, prominence_sigma=prominence_sigma,
        distance=distance, max_peaks=max_peaks,
    )

    points: list[EfficiencyPoint] = []
    for line in source.lines:
        energy = float(line["energy_kev"])
        yield_fraction = float(line["yield"])
        parent = str(line["parent"])
        best = min(
            (p for p in peaks if p.energy_kev is not None),
            key=lambda p: abs(p.energy_kev - energy),
            default=None,
        )
        if best is None or abs(best.energy_kev - energy) > tolerance_kev or best.net_area <= min_net_area:
            continue
        parent_activity = activities.get(parent, 0.0)
        denominator = parent_activity * yield_fraction * spectrum.live_time
        if denominator <= 0:
            continue
        efficiency = best.net_area / denominator
        points.append(
            EfficiencyPoint(
                energy_kev=energy,
                efficiency=efficiency,
                parent=parent,
                yield_fraction=yield_fraction,
                excluded=energy in source.excluded_energies,
            )
        )
    points.sort(key=lambda p: p.energy_kev)
    return points
