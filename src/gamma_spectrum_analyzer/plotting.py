from __future__ import annotations

from pathlib import Path

import numpy as np

from .efficiency import EfficiencyCurve
from .models import Calibration, Peak, Spectrum


def save_plot(
    spectrum: Spectrum,
    peaks: list[Peak],
    output: str | Path,
    x_axis: str = "energy",
    log_y: bool = False,
    calibration: Calibration | None = None,
) -> None:
    import matplotlib.pyplot as plt

    if x_axis == "energy" and calibration is not None:
        x = calibration.energy(spectrum.channels)
        xlabel = "Energy (keV)"
    else:
        x = spectrum.channels
        xlabel = "Channel"

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(x, spectrum.counts, lw=0.9, color="#2f80ed")
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Counts")
    ax.grid(True, ls="--", alpha=0.45)
    for peak in peaks:
        xpos = peak.channel if xlabel == "Channel" else peak.energy_kev
        if xpos is None:
            continue
        ypos = spectrum.counts[int(round(peak.channel))]
        label_energy = peak.matched_energy_kev or peak.energy_kev
        label = f"{peak.nuclide}:{label_energy:.2f}" if peak.nuclide and label_energy else ""
        ax.axvline(xpos, color="#e91e63", lw=0.8, alpha=0.7)
        if label:
            ax.annotate(label, xy=(xpos, ypos), xytext=(0, 16), textcoords="offset points",
                        ha="center", fontsize=8, arrowprops={"arrowstyle": "-|>", "lw": 0.6})
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)


def save_eff_curve_plot(curve: EfficiencyCurve, output: str | Path, log_y: bool = False) -> None:
    """Plot the measured efficiency points and the piecewise log-log curve."""
    import matplotlib.pyplot as plt

    energies = [p.energy_kev for p in curve.used]
    efficiencies = [p.efficiency for p in curve.used]
    excluded_e = [p.energy_kev for p in curve.points if p.excluded]
    excluded_eff = [p.efficiency for p in curve.points if p.excluded]

    fig, ax = plt.subplots(figsize=(10, 6))
    sample = np.linspace(min(energies), max(energies), 200)
    ax.plot(sample, [curve.efficiency_at(e) for e in sample], "-", color="#2f80ed", lw=1.2,
            label="Piecewise log-log interpolation")
    ax.scatter(energies, efficiencies, s=55, zorder=5, color="#27ae60",
               label="Used points", edgecolor="k", linewidth=0.5)
    if excluded_e:
        ax.scatter(excluded_e, excluded_eff, s=55, marker="x", zorder=5, color="#e74c3c",
                   label="Excluded (self-absorption / natural K-40)")
    if log_y:
        ax.set_yscale("log")
    ax.set_xscale("log")
    ax.set_xlabel("Energy (keV)")
    ax.set_ylabel(r"Detection efficiency $\varepsilon$")
    ax.set_title(f"Efficiency curve — {curve.used[0].energy_kev:.0f}–{curve.used[-1].energy_kev:.0f} keV "
                 f"({len(curve.used)} points)")
    ax.grid(True, which="both", ls="--", alpha=0.45)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=180)
    plt.close(fig)
