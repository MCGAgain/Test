from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .calibration import (
    auto_energy_calibration,
    load_calibration,
    save_calibration,
    train_energy_calibration,
)
from .efficiency import CalibrationSource, EfficiencyCurve, fit_efficiency_points
from .identify import build_complete_nuclide_peaks, identify_peaks
from .io import read_spectrum
from .library import RTK_QUANTIFICATION_LINES
from .peaks import find_and_fit_peaks
from .plotting import save_eff_curve_plot, save_plot
from .quantify import fill_quantification, quantify_specific_activity
from .report import rich_peak_table, rich_rtk_table, write_peak_csv, write_rtk_csv
from .resources import builtin_calibration_path, builtin_efficiency_path

app = typer.Typer(help="Gamma spectrum recognition and analysis.")
console = Console()


@app.command()
def train(
    standards_dir: Path = typer.Argument(..., help="Directory containing the five standard spectrum folders."),
    output: Path = typer.Option(Path("calibration.json"), "--output", "-o", help="Calibration JSON output."),
) -> None:
    """Train quadratic energy calibration from the five reference spectra."""
    calibration, used = train_energy_calibration(standards_dir)
    save_calibration(calibration, output, used)
    console.print(f"[green]Saved calibration:[/] {output}")
    console.print(f"Energy: E = {calibration.energy_coefficients[0]:.8g} + "
                  f"{calibration.energy_coefficients[1]:.8g}*CH + "
                  f"{calibration.energy_coefficients[2]:.8g}*CH^2")
    console.print(f"Used standard peaks: {len(used)}")


@app.command()
def analyze(
    spectrum_file: Path = typer.Argument(..., help="Unknown .xls/.csv/.txt/.spe spectrum file."),
    calibration_file: Path | None = typer.Option(None, "--calibration", "-c", help="Custom calibration JSON file."),
    output_csv: Path = typer.Option(Path("peak_table.csv"), "--csv", help="Peak table CSV output."),
    output_plot: Path | None = typer.Option(Path("spectrum.png"), "--plot", help="Annotated plot PNG output."),
    tolerance_kev: float = typer.Option(2.0, "--tolerance", help="Nuclide matching tolerance in keV."),
    prominence_sigma: float = typer.Option(3.0, "--prominence-sigma", help="Peak search sensitivity. Lower finds weaker peaks."),
    log_y: bool = typer.Option(False, "--log-y", help="Use logarithmic Y axis in plot."),
    auto_calibrate: bool = typer.Option(
        True, "--auto-calibrate/--no-auto-calibrate", help="Derive the energy calibration from this spectrum.",
    ),
) -> None:
    """Analyze an unknown spectrum and output a screenshot-style peak table."""
    spectrum = read_spectrum(spectrum_file)
    if calibration_file is not None and Path(calibration_file).exists():
        calibration = load_calibration(calibration_file)
        console.print(f"[green]Loaded calibration:[/] {calibration_file} "
                      f"(E = {calibration.energy_coefficients[0]:.6g} + "
                      f"{calibration.energy_coefficients[1]:.6g}*CH + "
                      f"{calibration.energy_coefficients[2]:.6g}*CH^2)")
    elif auto_calibrate or calibration_file is None:
        calibration = auto_energy_calibration(spectrum)
        console.print(f"[green]Self-adaptive calibration:[/] E = {calibration.energy_coefficients[0]:.6g} + "
                      f"{calibration.energy_coefficients[1]:.6g}*CH + "
                      f"{calibration.energy_coefficients[2]:.6g}*CH^2")
    else:
        cal_path = builtin_calibration_path()
        calibration = load_calibration(cal_path)
    peaks = find_and_fit_peaks(spectrum, calibration, prominence_sigma=prominence_sigma)
    confirmed = identify_peaks(peaks, tolerance_kev, spectrum=spectrum)
    if confirmed:
        peaks = build_complete_nuclide_peaks(spectrum, calibration, peaks, confirmed, tolerance_kev=tolerance_kev)
    activity_summary = fill_quantification(peaks, spectrum, calibration)
    write_peak_csv(peaks, output_csv)
    if output_plot:
        save_plot(spectrum, peaks, output_plot, calibration=calibration, log_y=log_y)

    console.print(rich_peak_table(peaks))
    console.print(f"[green]Saved peak CSV:[/] {output_csv}")
    if output_plot:
        console.print(f"[green]Saved plot:[/] {output_plot}")
    if confirmed:
        console.print("[bold]Confirmed nuclides:[/] " + ", ".join(sorted(confirmed)))
    else:
        console.print("[yellow]No nuclides passed confirmation rules.[/]")
    if activity_summary:
        for nuclide, item in activity_summary.items():
            console.print(f"{nuclide}: {item['activity_bq']:.6g} Bq ± {item['activity_uncert_percent']:.3g}%")
    else:
        console.print("[yellow]Activity is blank because no efficiency calibration is available yet.[/]")


@app.command()
def rtk(
    samples_dir: Path = typer.Argument(..., help="Directory containing the Ra/Th/K sample spectra (镭钍钾*.xls)."),
    cal_spectrum: Path = typer.Argument(..., help="The calibration-source spectrum file (e.g. 土壤监测效率校准源.xls)."),
    masses: str = typer.Option(
        ..., "--masses", "-m",
        help="Comma-separated sample masses in kg, same order as the sorted files in samples_dir.",
    ),
    cal_info: Path = typer.Option(
        Path("efficiency_7ntr1024.json"), "--cal-info",
        help="Calibration-source info JSON (defaults to the bundled 7NTR-1024 source).",
    ),
    output_csv: Path = typer.Option(Path("rtk_report.csv"), "--csv", help="Ra/Th/K report CSV output."),
    output_plot: Path | None = typer.Option(Path("efficiency_curve.png"), "--plot", help="Efficiency curve plot PNG."),
    prominence_sigma: float = typer.Option(3.0, "--prominence-sigma", help="Peak search sensitivity."),
    log_y: bool = typer.Option(False, "--log-y", help="Use logarithmic Y axis in the efficiency plot."),
) -> None:
    """Compute Ra-226 / Th-232 / K-40 specific activities (Bq/kg) for soil samples.

    Builds a piecewise log-log efficiency curve from the calibration-source
    spectrum (activities decay-corrected from the certificate reference date to
    the measurement DATE), then quantifies each sample against it:
        C_s = N_net / (epsilon(E) * P_gamma * t_live * m)
    Ra-226 via Bi-214 609.3 keV, Th-232 via Tl-208 583.2 keV (the 2614.5 keV
    line is out of the 8192-channel ADC range), K-40 via its 1460.8 keV line.
    """
    source_path = cal_info
    if not Path(source_path).exists():
        source_path = builtin_efficiency_path()
        console.print(f"[yellow]cal-info '{cal_info}' not found; using bundled 7NTR-1024 source instead.[/]")
    source = CalibrationSource.from_json(source_path)

    cal_spec = read_spectrum(cal_spectrum)
    cal = auto_energy_calibration(cal_spec)
    console.print(f"[green]Calibration-source auto calibration:[/] "
                  f"E = {cal.energy_coefficients[0]:.6g} + {cal.energy_coefficients[1]:.6g}*CH")
    points = fit_efficiency_points(cal_spec, source, cal, prominence_sigma=prominence_sigma)
    if not points:
        raise RuntimeError("No usable efficiency points measured from the calibration source.")
    curve = EfficiencyCurve(points)
    console.print(f"[green]Efficiency curve:[/] {len(curve.used)} used points "
                  f"({len(points) - len(curve.used)} excluded, {', '.join(f'{p.energy_kev:.1f}' for p in curve.points if p.excluded) or 'none'})")
    if output_plot:
        save_eff_curve_plot(curve, output_plot, log_y=log_y)

    mass_list = [float(m.strip()) for m in masses.split(",")]
    files = sorted(Path(samples_dir).glob("*.xls"))
    if len(files) != len(mass_list):
        raise RuntimeError(f"Found {len(files)} sample files but {len(mass_list)} masses. "
                           f"Provide one --masses value per sorted file: "
                           f"{', '.join(f.name for f in files)}")

    rows: list[dict] = []
    for file, mass in zip(files, mass_list):
        spec = read_spectrum(file)
        spec_cal = auto_energy_calibration(spec)
        peaks = find_and_fit_peaks(spec, spec_cal, prominence_sigma=prominence_sigma)
        quantities = quantify_specific_activity(
            peaks, spec.live_time, curve, mass, RTK_QUANTIFICATION_LINES
        )
        for nuclide, item in quantities.items():
            rows.append({
                "sample": file.name,
                "nuclide": nuclide,
                "mass_kg": item["mass_kg"],
                "activity_bq": item["activity_bq"],
                "specific_activity_bq_per_kg": item["specific_activity_bq_per_kg"],
                "uncert_percent": item["activity_uncert_percent"],
            })
        missing = set(RTK_QUANTIFICATION_LINES) - set(quantities)
        if missing:
            console.print(f"[yellow]{file.name}: no result for {', '.join(sorted(missing))}[/]")

    if not rows:
        raise RuntimeError("No Ra/Th/K peaks found in any sample — check prominence_sigma.")
    write_rtk_csv(rows, output_csv)
    console.print(rich_rtk_table(rows))
    console.print(f"[green]Saved Ra/Th/K report:[/] {output_csv}")


@app.command()
def gui() -> None:
    """Open the desktop GUI."""
    from .gui import main

    main()


if __name__ == "__main__":
    app()
