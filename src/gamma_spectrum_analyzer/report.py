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


RTK_HEADERS = [
    "样品", "核素", "样品量(kg)", "活度(Bq)", "比活度(Bq/kg)", "不确定度(%)",
]


def rtk_rows(rows: list[dict]) -> list[list[str]]:
    return [[
        row.get("sample", ""),
        row.get("nuclide", ""),
        _fmt(row.get("mass_kg"), 4),
        _fmt(row.get("activity_bq"), 4),
        _fmt(row.get("specific_activity_bq_per_kg"), 4),
        _fmt(row.get("uncert_percent"), 3),
    ] for row in rows]


def write_rtk_csv(rows: list[dict], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(RTK_HEADERS)
        writer.writerows(rtk_rows(rows))


def rich_rtk_table(rows: list[dict]) -> Table:
    table = Table(title="镭钍钾比活度分析结果（GB/T 11743-2013）")
    for header in RTK_HEADERS:
        table.add_column(header, overflow="fold")
    for row in rtk_rows(rows):
        table.add_row(*row)
    return table


def _fmt(value, digits: int) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)
