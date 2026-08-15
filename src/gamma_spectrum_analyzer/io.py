from __future__ import annotations

import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from .models import Spectrum


def read_spectrum(path: str | Path) -> Spectrum:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".spe":
        return _read_spe(path)
    if suffix in {".csv", ".txt"}:
        return _read_csv_like(path)
    if suffix == ".xls":
        return _read_xls(path)
    raise ValueError(f"Unsupported spectrum format: {path.suffix}")


def _read_xls(path: Path) -> Spectrum:
    try:
        import xlrd

        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_index(0)
        rows = [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
        return _rows_to_spectrum(rows, path)
    except Exception:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        if not soffice:
            raise RuntimeError("Reading .xls needs xlrd or LibreOffice/soffice on PATH.")
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "csv", "--outdir", td, str(path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            csv_path = next(Path(td).glob("*.csv"))
            return _read_csv_like(csv_path, original_path=path)


def _read_csv_like(path: Path, original_path: Path | None = None) -> Spectrum:
    rows: list[list[str]] = []
    with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        for row in csv.reader(f):
            rows.append(row)
    return _rows_to_spectrum(rows, original_path or path)


def _rows_to_spectrum(rows: list[list[object]], path: Path) -> Spectrum:
    channels: list[int] = []
    counts: list[float] = []
    metadata: dict[str, str] = {}
    live_time: float | None = None
    real_time: float | None = None

    for row in rows:
        if not row:
            continue
        first = str(row[0]).strip()
        second = str(row[1]).strip() if len(row) > 1 else ""

        meta_match = re.match(r"^([A-Za-z_]+)\s*=\s*(.*)$", first)
        if meta_match:
            key, value = meta_match.group(1).upper(), meta_match.group(2) or second
            metadata[key] = value
            if key == "TLIVE":
                live_time = _to_float(value)
            elif key == "TREAL":
                real_time = _to_float(value)
            continue

        ch = _to_float(first)
        ct = _to_float(second)
        if ch is not None and ct is not None and ch >= 0:
            channels.append(int(ch))
            counts.append(float(ct))

    if not channels:
        raise ValueError(f"No channel/count rows found in {path}")
    return Spectrum(
        channels=np.asarray(channels, dtype=float),
        counts=np.asarray(counts, dtype=float),
        live_time=live_time,
        real_time=real_time,
        path=path,
        metadata=metadata,
    )


def _read_spe(path: Path) -> Spectrum:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    counts: list[float] = []
    live_time = None
    real_time = None
    metadata: dict[str, str] = {}
    in_data = False

    for line in lines:
        text = line.strip()
        if not text:
            continue
        if text.startswith("$MEAS_TIM"):
            in_data = False
            continue
        if text.startswith("$DATA"):
            in_data = True
            continue
        if text.startswith("$"):
            in_data = False
            continue
        if live_time is None and real_time is None and re.match(r"^\d+(\.\d+)?\s+\d+(\.\d+)?$", text):
            real_time, live_time = map(float, text.split()[:2])
            continue
        if in_data:
            parts = text.split()
            if len(parts) == 2 and all(p.lstrip("+-").isdigit() for p in parts):
                continue
            for part in parts:
                val = _to_float(part)
                if val is not None:
                    counts.append(val)

    if not counts:
        raise ValueError(f"No spectrum counts found in {path}")
    channels = np.arange(len(counts), dtype=float)
    return Spectrum(channels, np.asarray(counts, dtype=float), live_time, real_time, path, metadata)


def _to_float(value: object) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return float(text)
    except Exception:
        return None
