from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GammaLine:
    nuclide: str
    energy_kev: float
    yield_percent: float

    @property
    def yield_fraction(self) -> float:
        return self.yield_percent / 100.0


NUCLIDE_LIBRARY: dict[str, list[GammaLine]] = {
    "Co-60": [
        GammaLine("Co-60", 1173.23, 99.85),
        GammaLine("Co-60", 1332.49, 99.98),
    ],
    "Eu-152": [
        GammaLine("Eu-152", 121.78, 28.53),
        GammaLine("Eu-152", 244.70, 7.55),
        GammaLine("Eu-152", 344.28, 26.59),
        GammaLine("Eu-152", 778.90, 12.93),
        GammaLine("Eu-152", 964.08, 14.51),
        GammaLine("Eu-152", 1112.08, 13.67),
        GammaLine("Eu-152", 1408.01, 20.87),
    ],
    "I-131": [
        GammaLine("I-131", 284.31, 6.12),
        GammaLine("I-131", 364.49, 81.5),
        GammaLine("I-131", 636.99, 7.16),
    ],
    "Cs-137": [
        GammaLine("Cs-137", 661.66, 85.13),
    ],
    "Ba-133": [
        GammaLine("Ba-133", 81.00, 32.9),
        GammaLine("Ba-133", 356.01, 62.0),
    ],
}


CONFIRMATION_RULES = {
    "Co-60": {"required_energies": [1173.23, 1332.49], "min_matches": 2},
    "Eu-152": {"required_energies": [], "min_matches": 3},
    "I-131": {"required_energies": [364.49], "min_matches": 2},
    "Cs-137": {"required_energies": [], "min_matches": 1},
    "Ba-133": {"required_energies": [], "min_matches": 2},
}


STANDARD_EXPECTED_LINES = {
    "Co-60": [1173.23, 1332.49],
    "Eu-152": [121.78, 244.70, 344.28, 778.90, 964.08, 1112.08, 1408.01],
    # I-131 636.99 keV is weak in the provided spreadsheet and can be pulled onto
    # the Cs-137 661.66 keV peak, so it is kept in the nuclide library but not as
    # an energy-calibration anchor.
    "Cs-137+I-131": [284.31, 364.49, 661.66],
    "Cs-137+Ba-133": [81.00, 356.01, 661.66],
    "Co-60+Eu-152": [121.78, 244.70, 344.28, 778.90, 964.08, 1112.08, 1173.23, 1332.49, 1408.01],
}


def all_lines() -> list[GammaLine]:
    return [line for lines in NUCLIDE_LIBRARY.values() for line in lines]
