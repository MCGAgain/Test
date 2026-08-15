from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .calibration import load_calibration, save_calibration, train_energy_calibration
from .identify import identify_peaks
from .io import read_spectrum
from .peaks import find_and_fit_peaks
from .plotting import save_plot
from .quantify import fill_quantification
from .report import rich_peak_table, write_peak_csv

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
    calibration_file: Path = typer.Option(Path("calibration.json"), "--calibration", "-c"),
    output_csv: Path = typer.Option(Path("peak_table.csv"), "--csv", help="Peak table CSV output."),
    output_plot: Path | None = typer.Option(Path("spectrum.png"), "--plot", help="Annotated plot PNG output."),
    tolerance_kev: float = typer.Option(2.0, "--tolerance", help="Nuclide matching tolerance in keV."),
    prominence_sigma: float = typer.Option(4.0, "--prominence-sigma", help="Peak search sensitivity. Lower finds weaker peaks."),
    log_y: bool = typer.Option(False, "--log-y", help="Use logarithmic Y axis in plot."),
) -> None:
    """Analyze an unknown spectrum and output a screenshot-style peak table."""
    calibration = load_calibration(calibration_file)
    spectrum = read_spectrum(spectrum_file)
    peaks = find_and_fit_peaks(spectrum, calibration, prominence_sigma=prominence_sigma)
    confirmed = identify_peaks(peaks, tolerance_kev)
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
def gui() -> None:
    """Open the desktop GUI."""
    from .gui import main

    main()


if __name__ == "__main__":
    app()
