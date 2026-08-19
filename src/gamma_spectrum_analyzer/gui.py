from __future__ import annotations

import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .calibration import auto_energy_calibration, load_calibration
from .efficiency import CalibrationSource, EfficiencyCurve, fit_efficiency_points
from .identify import identify_peaks
from .io import read_spectrum
from .library import RTK_QUANTIFICATION_LINES
from .models import Calibration, Peak, Spectrum
from .peaks import find_and_fit_peaks
from .quantify import fill_quantification, quantify_specific_activity
from .report import HEADERS, peak_rows, write_peak_csv
from .resources import builtin_calibration_path, builtin_efficiency_path


class GammaGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("γ能谱识别分析软件")
        self.geometry("1280x780")
        self.spectrum: Spectrum | None = None
        self.calibration: Calibration | None = self._load_builtin_calibration()
        if self.calibration is not None:
            self.title("γ能谱识别分析软件（内置刻度已加载）")
        self.peaks: list[Peak] = []
        self.x_mode = tk.StringVar(value="energy")
        self.log_y = tk.BooleanVar(value=False)
        self.auto_calibrate = tk.BooleanVar(value=True)
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
        ttk.Button(toolbar, text="镭钍钾分析", command=self.analyze_rtk).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(toolbar, text="能量", variable=self.x_mode, value="energy", command=self.redraw).pack(side=tk.LEFT, padx=8)
        ttk.Radiobutton(toolbar, text="道号", variable=self.x_mode, value="channel", command=self.redraw).pack(side=tk.LEFT)
        ttk.Checkbutton(toolbar, text="log Y", variable=self.log_y, command=self.redraw).pack(side=tk.LEFT, padx=8)
        ttk.Checkbutton(toolbar, text="自动刻度", variable=self.auto_calibrate).pack(side=tk.LEFT, padx=8)

        self.fig = Figure(figsize=(12, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)

        ttk.Label(self, textvariable=self.status, anchor=tk.W).pack(fill=tk.X, padx=6, pady=3)

    def _load_builtin_calibration(self) -> Calibration | None:
        """Try to load the calibration JSON bundled with the executable."""
        path = builtin_calibration_path()
        try:
            return load_calibration(path)
        except Exception:
            return None

    def load_calibration(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Calibration", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.calibration = load_calibration(path)
        self.auto_calibrate.set(False)
        self.title("γ能谱识别分析软件（自定义刻度）")
        messagebox.showinfo("刻度", "刻度加载完成")

    def load_spectrum(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Spectrum", "*.xls *.csv *.txt *.spe"), ("All files", "*.*")])
        if not path:
            return
        self.current_filename = Path(path).name
        self.spectrum = read_spectrum(path)
        if self.auto_calibrate.get():
            try:
                self.calibration = auto_energy_calibration(self.spectrum)
                a0, a1, a2 = self.calibration.energy_coefficients
                self.title(f"γ能谱识别分析软件 - [{self.current_filename}]（自动刻度：E = {a0:.3f} + {a1:.5f}*CH）")
            except Exception:
                self.title(f"γ能谱识别分析软件 - [{self.current_filename}]")
        else:
            self.title(f"γ能谱识别分析软件 - [{self.current_filename}]")
        self.peaks = []
        self.redraw()

    def analyze(self) -> None:
        if self.spectrum is None:
            messagebox.showwarning("提示", "请先导入谱文件")
            return
        if self.auto_calibrate.get() or self.calibration is None:
            try:
                self.calibration = auto_energy_calibration(self.spectrum)
                a0, a1, a2 = self.calibration.energy_coefficients
                fname = getattr(self, "current_filename", "")
                self.title(f"γ能谱识别分析软件 - [{fname}]（自适应刻度：E = {a0:.3f} + {a1:.5f}*CH）")
            except Exception as exc:
                messagebox.showerror("自动刻度", f"自动能量刻度失败：{exc}")
                return
        calibration = self.calibration
        self.peaks = find_and_fit_peaks(self.spectrum, calibration, prominence_sigma=3.0)
        identify_peaks(self.peaks)
        fill_quantification(self.peaks, self.spectrum, calibration)
        self.redraw()
        self.show_peak_window()

    def analyze_rtk(self) -> None:
        """镭钍钾比活度分析：用 7NTR-1024 校准源刻度效率曲线，对当前谱算 Ra/Th/K。"""
        if self.spectrum is None:
            messagebox.showwarning("提示", "请先在主界面导入待测土壤样品谱（如 镭钍钾1.xls）")
            return
        fname = getattr(self, "current_filename", "待测样品")
        if "校准源" in fname:
            messagebox.showwarning("提示", "当前主界面打开的是【效率校准源】，请先打开【待测土壤样品谱】（如 镭钍钾1.xls）！")
            return

        cal_path = filedialog.askopenfilename(
            title="选择效率校准源谱文件（如 土壤监测效率校准源.xls）",
            filetypes=[("Spectrum", "*.xls *.csv *.txt *.spe"), ("All files", "*.*")],
        )
        if not cal_path:
            return
        try:
            cal_spec = read_spectrum(cal_path)
            source = CalibrationSource.from_json(builtin_efficiency_path())
            cal = auto_energy_calibration(cal_spec)
            points = fit_efficiency_points(cal_spec, source, cal)
            curve = EfficiencyCurve(points)

            default_mass = "0.300"
            if "1" in fname:
                default_mass = "0.334"
            elif "2" in fname:
                default_mass = "0.245"
            elif "3" in fname:
                default_mass = "0.244"
            elif "4" in fname:
                default_mass = "0.264"
            elif "5" in fname:
                default_mass = "0.310"

            mass_input = simpledialog.askstring("样品量", f"当前待测样品：{fname}\n请输入样品质量 m (kg)：", initialvalue=default_mass)
            if not mass_input:
                return
            mass = float(mass_input)
            if mass <= 0:
                raise ValueError("样品质量必须为正数")
            peaks = find_and_fit_peaks(self.spectrum, auto_energy_calibration(self.spectrum), prominence_sigma=3.0)
            quantities = quantify_specific_activity(
                peaks, self.spectrum.live_time, curve, mass, RTK_QUANTIFICATION_LINES
            )
        except Exception as exc:
            messagebox.showerror("镭钍钾分析", f"分析失败：{exc}")
            return
        if not quantities:
            messagebox.showwarning("镭钍钾分析", "未在谱中找到 Ra-226/Th-232/K-40 特征峰")
            return
        lines = [f"{n}: 比活度 {q['specific_activity_bq_per_kg']:.2f} Bq/kg (活度 {q['activity_bq']:.4f} Bq, 不确定度 {q['activity_uncert_percent']:.2f}%)" for n, q in quantities.items()]
        messagebox.showinfo("镭钍钾比活度分析结果", f"样品：{fname}\n样品量 m = {mass:.4f} kg\n\n" + "\n".join(lines))

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
