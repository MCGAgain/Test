from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .calibration import load_calibration
from .identify import identify_peaks
from .io import read_spectrum
from .models import Calibration, Peak, Spectrum
from .peaks import find_and_fit_peaks
from .quantify import fill_quantification
from .report import HEADERS, peak_rows, write_peak_csv


class GammaGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("γ能谱识别分析软件")
        self.geometry("1280x780")
        self.spectrum: Spectrum | None = None
        self.calibration: Calibration | None = None
        self.peaks: list[Peak] = []
        self.x_mode = tk.StringVar(value="energy")
        self.log_y = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Time: 0 | Cps: 0 | Channel: 0 | Counts: 0 | Energy: 0.00 | FWHM: 0 Ch | ROI Area: 0 | ROI LR: 0|0")
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=8, pady=6)
        ttk.Button(toolbar, text="加载刻度", command=self.load_calibration).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="导入谱", command=self.load_spectrum).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="分析", command=self.analyze).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="峰信息", command=self.show_peak_window).pack(side=tk.LEFT, padx=3)
        ttk.Button(toolbar, text="保存CSV", command=self.save_csv).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(toolbar, text="能量", variable=self.x_mode, value="energy", command=self.redraw).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(toolbar, text="道号", variable=self.x_mode, value="channel", command=self.redraw).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="log Y", variable=self.log_y, command=self.redraw).pack(side=tk.LEFT, padx=8)

        self.fig = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

        ttk.Label(self, textvariable=self.status, anchor=tk.W).pack(fill=tk.X, padx=6, pady=3)

    def load_calibration(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Calibration", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.calibration = load_calibration(path)
        messagebox.showinfo("刻度", "刻度加载完成")

    def load_spectrum(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Spectrum", "*.xls *.csv *.txt *.spe"), ("All files", "*.*")])
        if not path:
            return
        self.spectrum = read_spectrum(path)
        self.peaks = []
        self.redraw()

    def analyze(self) -> None:
        if self.spectrum is None:
            messagebox.showwarning("提示", "请先导入谱文件")
            return
        if self.calibration is None:
            messagebox.showwarning("提示", "请先加载 calibration.json")
            return
        self.peaks = find_and_fit_peaks(self.spectrum, self.calibration, prominence_sigma=4.0)
        identify_peaks(self.peaks)
        fill_quantification(self.peaks, self.spectrum, self.calibration)
        self.redraw()
        self.show_peak_window()

    def redraw(self) -> None:
        self.ax.clear()
        if self.spectrum is None:
            self.ax.set_xlabel("Channel")
            self.ax.set_ylabel("Counts")
            self.canvas.draw_idle()
            return
        if self.x_mode.get() == "energy" and self.calibration is not None:
            x = self.calibration.energy(self.spectrum.channels)
            xlabel = "Energy (keV)"
        else:
            x = self.spectrum.channels
            xlabel = "Channel"
        self.ax.plot(x, self.spectrum.counts, color="#2f80ed", lw=0.9)
        self.ax.grid(True, ls="--", alpha=0.45)
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel("Counts")
        if self.log_y.get():
            self.ax.set_yscale("log")
        for peak in self.peaks:
            xpos = peak.energy_kev if xlabel.startswith("Energy") else peak.channel
            if xpos is None:
                continue
            ypos = self.spectrum.counts[int(round(peak.channel))]
            label_energy = peak.matched_energy_kev or peak.energy_kev
            label = f"{peak.nuclide}:{label_energy:.2f}" if peak.nuclide and label_energy else ""
            self.ax.axvline(xpos, color="#e91e63", lw=0.8, alpha=0.7)
            if label:
                self.ax.annotate(label, xy=(xpos, ypos), xytext=(0, 16), textcoords="offset points",
                                 ha="center", fontsize=8, arrowprops={"arrowstyle": "-|>", "lw": 0.6})
        self.fig.tight_layout()
        self.canvas.draw_idle()

    def show_peak_window(self) -> None:
        win = tk.Toplevel(self)
        win.title("峰信息")
        win.geometry("1120x360")
        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        tree = ttk.Treeview(frame, columns=HEADERS, show="headings", height=12)
        xbar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        ybar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        for header in HEADERS:
            tree.heading(header, text=header)
            tree.column(header, width=110, anchor=tk.CENTER)
        for row in peak_rows(self.peaks):
            tree.insert("", tk.END, values=row)
        tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        ttk.Button(win, text="保存", command=self.save_csv).pack(anchor=tk.E, padx=10, pady=8)

    def save_csv(self) -> None:
        if not self.peaks:
            messagebox.showwarning("提示", "还没有峰表")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            write_peak_csv(self.peaks, path)
            messagebox.showinfo("保存", "峰表已保存")

    def _on_motion(self, event) -> None:
        if self.spectrum is None or event.xdata is None:
            return
        if self.x_mode.get() == "energy" and self.calibration is not None:
            ch = int(round(self.calibration.channel_from_energy(float(event.xdata))))
            energy = float(event.xdata)
        else:
            ch = int(round(event.xdata))
            energy = float(self.calibration.energy(ch)) if self.calibration else 0.0
        if 0 <= ch < len(self.spectrum.counts):
            counts = self.spectrum.counts[ch]
            live = self.spectrum.live_time or 0.0
            cps = counts / live if live else 0.0
            self.status.set(f"Time: {live:.3f} | Cps: {cps:.3f} | Channel: {ch} | Counts: {counts:.0f} | "
                            f"Energy: {energy:.2f} | FWHM: 0 Ch | ROI Area: 0 | ROI LR: 0|0")


def main() -> None:
    app = GammaGui()
    app.mainloop()


if __name__ == "__main__":
    main()
