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
        GammaLine("Co-60", 1332.49, 99.9826),
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
    "U-238": [
        GammaLine("U-238", 63.29, 3.7),        # 子体 Th-234
        GammaLine("U-238", 92.38, 2.13),       # 子体 Th-234
        GammaLine("U-238", 1001.03, 0.845),    # 子体 Pa-234m
    ],
    "U-235": [
        GammaLine("U-235", 84.21, 6.6),
        GammaLine("U-235", 143.76, 10.96),
        GammaLine("U-235", 163.36, 5.08),
        GammaLine("U-235", 185.72, 57.2),
        GammaLine("U-235", 205.31, 5.01),
    ],
    "Ra-226": [
        GammaLine("Ra-226", 295.21, 18.4),     # 子体 Pb-214
        GammaLine("Ra-226", 351.92, 35.6),     # 子体 Pb-214
        GammaLine("Ra-226", 609.31, 44.8),     # 子体 Bi-214
        GammaLine("Ra-226", 1120.29, 14.9),    # 子体 Bi-214
        GammaLine("Ra-226", 1764.49, 15.3),    # 子体 Bi-214
    ],
    "Th-232": [
        GammaLine("Th-232", 238.63, 43.6),     # 子体 Pb-212
        GammaLine("Th-232", 338.32, 11.3),     # 子体 Ac-228
        GammaLine("Th-232", 583.19, 85.5),     # 子体 Tl-208
        GammaLine("Th-232", 911.20, 25.8),     # 子体 Ac-228
        GammaLine("Th-232", 969.11, 15.8),     # 子体 Ac-228
    ],
    "K-40": [
        GammaLine("K-40", 1460.83, 10.66),
    ],
}


CONFIRMATION_RULES = {
    "Co-60": {"required_energies": [1173.23], "min_matches": 1},
    "Eu-152": {"required_energies": [121.78], "min_matches": 3},
    "I-131": {"required_energies": [364.49], "min_matches": 1},
    "Cs-137": {"required_energies": [661.66], "min_matches": 1},
    "Ba-133": {"required_energies": [356.01, 81.00], "min_matches": 2},
    "U-238": {"required_energies": [], "min_matches": 1},
    "U-235": {"required_energies": [], "min_matches": 1},
    "Ra-226": {"required_energies": [609.31], "min_matches": 3},
    "Th-232": {"required_energies": [583.19], "min_matches": 3},
    "K-40": {"required_energies": [1460.83], "min_matches": 1},
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


# Strong, well-separated gamma lines used by :func:`auto_energy_calibration`.
# (energy_kev, yield_fraction, origin) — covers the standard sources, the
# 7NTR-1024 calibration source and the soil Ra/Th/K samples with one list so a
# per-spectrum gain-based match always converges to the right calibration.
AUTO_CALIBRATION_LINES: list[tuple[float, float, str]] = [
    (59.54, 0.3578, "Am-241"),
    (81.00, 0.329, "Ba-133"),
    (121.78, 0.2853, "Eu-152"),
    (238.63, 0.436, "Pb-212/Th-232"),
    (244.70, 0.0755, "Eu-152"),
    (295.21, 0.184, "Pb-214/Ra-226"),
    (338.32, 0.113, "Ac-228/Th-232"),
    (344.28, 0.2659, "Eu-152"),
    (351.92, 0.356, "Pb-214/Ra-226"),
    (356.01, 0.620, "Ba-133"),
    (364.49, 0.815, "I-131"),
    (583.19, 0.855, "Tl-208/Th-232"),
    (609.31, 0.448, "Bi-214/Ra-226"),
    (661.66, 0.8513, "Cs-137"),
    (778.90, 0.1293, "Eu-152"),
    (911.20, 0.258, "Ac-228/Th-232"),
    (1173.23, 0.9985, "Co-60"),
    (1332.49, 0.9998, "Co-60"),
    (1408.01, 0.2087, "Eu-152"),
    (1460.83, 0.1066, "K-40"),
    (1764.49, 0.153, "Bi-214/Ra-226"),
]


# Lines used for the Ra/Th/K specific-activity task.
#   Ra-226: Bi-214 609.3 keV（子体久平衡）
#   Th-232: Tl-208 583.2 keV —— 2614.5 keV 超出 8192 道 ADC 量程（0.297 keV/ch × 8192 ≈ 2435 keV），
#           国标惯用 208Tl 高能线在此数据上不可用，参考结果与 583.2 keV 完全一致，故采用之。
#   K-40:   1460.8 keV 直接测量
# 每条仅用一条主 γ 线（与竞赛参考软件一致）；quantify_specific_activity 支持多线加权，
# 需要更稳健时可在此增加 1120.29/1764.49（Ra）与 911.20（Th）等辅助线。
RTK_QUANTIFICATION_LINES: dict[str, list[tuple[float, float]]] = {
    "Ra-226": [(609.31, 0.448)],
    "Th-232": [(583.19, 0.855)],
    "K-40": [(1460.83, 0.1066)],
}


def all_lines() -> list[GammaLine]:
    return [line for lines in NUCLIDE_LIBRARY.values() for line in lines]
