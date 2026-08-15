from __future__ import annotations

from pathlib import Path

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
