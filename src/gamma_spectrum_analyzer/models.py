from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Spectrum:
    channels: np.ndarray
    counts: np.ndarray
    live_time: float | None = None
    real_time: float | None = None
    path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Peak:
    channel: float
    roi_l: int
    roi_r: int
    energy_kev: float | None
    fwhm_channel: float
    fwhm_kev: float | None
    roi_area: float
    net_area: float
    area_uncert_percent: float
    fwtm_channel: float | None = None
    fwtm_kev: float | None = None
    count_rate: float | None = None
    nuclide: str = ""
    yield_percent: float | None = None
    efficiency: float | None = None
    activity_bq: float | None = None
    activity_uncert_percent: float | None = None
    matched_energy_kev: float | None = None


@dataclass
class Calibration:
    energy_coefficients: list[float]
    efficiency_coefficients: list[float] | None = None

    def energy(self, channels: np.ndarray | float) -> np.ndarray | float:
        a0, a1, a2 = self.energy_coefficients
        return a0 + a1 * channels + a2 * np.asarray(channels) ** 2

    def channel_from_energy(self, energy_kev: float) -> float:
        a0, a1, a2 = self.energy_coefficients
        if abs(a2) < 1e-15:
            return (energy_kev - a0) / a1
        roots = np.roots([a2, a1, a0 - energy_kev])
        real_roots = [float(r.real) for r in roots if abs(r.imag) < 1e-6 and r.real >= 0]
        return min(real_roots) if real_roots else float("nan")

    def efficiency(self, energy_kev: float) -> float | None:
        if not self.efficiency_coefficients:
            return None
        x = np.log(float(energy_kev))
        log_eff = np.polyval(self.efficiency_coefficients, x)
        return float(np.exp(log_eff))
