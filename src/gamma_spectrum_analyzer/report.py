from __future__ import annotations

import csv
from pathlib import Path

from rich.table import Table

from .models import Peak


HEADERS = [
    "Channel", "ROI L", "ROI R", "Energy(keV)", "FWHM(Ch)", "FWHM(E)",
    "ROI Area", "Net Area", "Area Uncert(%)", "Nuclide", "Yield(%)",
    "Efficiency", "Activity(Bq)", "Activity Uncert(%)", "Count rate",
]


def peak_rows(peaks: list[Peak]) -> list[list[str]]:
    return [[
        _fmt(p.channel, 3),
        str(p.roi_l),
        str(p.roi_r),
        _fmt(p.energy_kev, 3),
        _fmt(p.fwhm_channel, 2),
        _fmt(p.fwhm_kev, 2),
        _fmt(p.roi_area, 0),
        _fmt(p.net_area, 0),
        _fmt(p.area_uncert_percent, 4),
        p.nuclide,
        _fmt(p.yield_percent, 3),
        _fmt(p.efficiency, 6),
        _fmt(p.activity_bq, 6),
        _fmt(p.activity_uncert_percent, 4),
        _fmt(p.count_rate, 3),
    ] for p in peaks]


def write_peak_csv(peaks: list[Peak], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerows(peak_rows(peaks))


def rich_peak_table(peaks: list[Peak]) -> Table:
    table = Table(title="峰信息")
    for header in HEADERS:
        table.add_column(header, overflow="fold")
    for row in peak_rows(peaks):
        table.add_row(*row)
    return table


def _fmt(value, digits: int) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)
