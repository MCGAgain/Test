from __future__ import annotations

import sys
from pathlib import Path


def builtin_calibration_path() -> Path:
    """Return the path to the calibration JSON bundled with the application.

    Works in three layouts:
    - PyInstaller onefile bundle: data files are unpacked to ``sys._MEIPASS``.
    - PyInstaller onedir bundle: ``__file__`` points into the bundle.
    - Source checkout: ``src/gamma_spectrum_analyzer/data/calibration.json``.
    """
    return _bundled("calibration.json")


def builtin_efficiency_path() -> Path:
    """Return the path to the bundled 7NTR-1024 calibration-source info JSON."""
    return _bundled("efficiency_7ntr1024.json")


def _bundled(filename: str) -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "gamma_spectrum_analyzer" / "data" / filename
    return Path(__file__).resolve().parent / "data" / filename
