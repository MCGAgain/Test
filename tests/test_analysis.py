import unittest
from pathlib import Path

from gamma_spectrum_analyzer.io import read_spectrum
from gamma_spectrum_analyzer.calibration import auto_energy_calibration
from gamma_spectrum_analyzer.peaks import find_and_fit_peaks
from gamma_spectrum_analyzer.identify import identify_peaks, build_complete_nuclide_peaks
from gamma_spectrum_analyzer.quantify import fill_quantification


class TestGammaSpectrumAnalysis(unittest.TestCase):
    def test_standard_sources(self):
        datasets = [
            ("核分析赛道/核素识别/标准源/Co-60/Co-60 点源.xls", ["Co-60"]),
            ("核分析赛道/核素识别/标准源/Eu-152/Eu-152 点源.xls", ["Eu-152"]),
            ("核分析赛道/核素识别/标准源/Co-60+Eu-152/Co-60  Eu-152混合点源.xls", ["Co-60", "Eu-152"]),
            ("核分析赛道/核素识别/标准源/Cs-137+Ba-133/Cs-137 Ba-133标准源.xls", ["Ba-133", "Cs-137"]),
            ("核分析赛道/核素识别/标准源/Cs-137+I-131/I-131 Cs-137 水样1.xls", ["Cs-137", "I-131"]),
        ]
        for path_str, expected in datasets:
            path = Path(path_str)
            if not path.exists():
                continue
            spec = read_spectrum(path)
            spec.filename = path_str
            cal = auto_energy_calibration(spec)
            peaks = find_and_fit_peaks(spec, cal)
            confirmed = identify_peaks(peaks, spectrum=spec)
            self.assertEqual(set(confirmed.keys()), set(expected), f"Failed for {path_str}")

    def test_test_samples(self):
        datasets = [
            ("核分析赛道/核素识别/测试样/测试样1/测试样1.xls", ["Co-60", "Cs-137", "U-235", "U-238"]),
            ("核分析赛道/核素识别/测试样/测试样2/测试样2.xls", ["Co-60", "Cs-137", "Eu-152", "U-235", "U-238"]),
            ("核分析赛道/核素识别/测试样/测试样3/测试样3.xls", ["Co-60", "Cs-137", "Eu-152", "U-235", "U-238"]),
            ("核分析赛道/核素识别/测试样/测试样4/测试样4.xls", ["Co-60", "Cs-137", "Eu-152", "U-235", "U-238"]),
            ("核分析赛道/核素识别/测试样/测试样5/测试样5.xls", ["Co-60", "Cs-137", "Eu-152", "U-235", "U-238"]),
        ]
        for path_str, expected in datasets:
            path = Path(path_str)
            if not path.exists():
                continue
            spec = read_spectrum(path)
            spec.filename = path_str
            cal = auto_energy_calibration(spec)
            peaks = find_and_fit_peaks(spec, cal)
            confirmed = identify_peaks(peaks, spectrum=spec)
            self.assertEqual(set(confirmed.keys()), set(expected), f"Failed for {path_str}")


if __name__ == "__main__":
    unittest.main()
