# γ能谱识别分析软件

基于 5 张训练谱定制的 Python 原型，支持：

- 读取 `.xls/.csv/.txt/.spe` 谱文件，解析 `channel/counts/TLIVE/TREAL`
- Savitzky-Golay 平滑 + SNIP 本底扣除
- 自动寻峰 + 高斯局部拟合
- 二次能量刻度 `E = a0 + a1*CH + a2*CH^2`
- 内置 Co-60、Eu-152、I-131、Cs-137、Ba-133 γ 特征库
- 按规则识别核素：Co-60 必须同时匹配 1173 和 1332 keV；Eu-152 至少 4 条峰
- 导出与截图字段对齐的峰表 CSV
- 生成带 `Nuclide:Energy` 标注的谱图
- Tkinter 桌面 GUI
- GitHub Actions 自动构建 Windows `.exe` 和 macOS `.dmg`

## 本地安装

```bash
cd /Users/Zhuanz/gamma-spectrum-analyzer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## 训练标准源

你的标准源目录结构应类似：

```text
/Users/Zhuanz/Downloads/标准源/
  Co-60/
  Eu-152/
  Cs-137+I-131/
  Cs-137+Ba-133/
  Co-60+Eu-152/
```

训练能量刻度：

```bash
gamma-spectra train /Users/Zhuanz/Downloads/标准源 -o calibration.json
```

这一步会从 5 张谱里找参考峰，拟合二次能量刻度，并保存 `calibration.json`。

## 分析未知谱

例如把 `Co-60+Eu-152` 混合谱当成图六待测样品：

```bash
gamma-spectra analyze "/Users/Zhuanz/Downloads/标准源/Co-60+Eu-152/Co-60  Eu-152混合点源.xls" \
  -c calibration.json \
  --csv output/peak_table.csv \
  --plot output/spectrum.png \
  --prominence-sigma 3.0
```

输出字段：

`Channel, ROI L, ROI R, Energy(keV), FWHM(Ch), FWHM(E), ROI Area, Net Area, Area Uncert(%), Nuclide, Yield(%), Efficiency, Activity(Bq), Activity Uncert(%), Count rate`

## 打开 GUI

```bash
gamma-spectra gui
# 或
gamma-spectra-gui
```

GUI 流程：

1. 加载 `calibration.json`
2. 导入未知谱 `.xls/.spe/.csv`
3. 点击“分析”
4. 查看“峰信息”
5. 保存 CSV

## 关于活度定量

当前文件里只有谱计数和测量时间，没有标准源已知活度 `A_ref`。因此本项目可以先完成能量刻度、寻峰、核素识别、峰面积和计数率。

绝对活度需要补充标准源活度后做效率刻度：

```text
efficiency = NetArea / (t_live * A_ref * Yield)
Activity = NetArea / (t_live * efficiency(E) * Yield)
```

`examples/standard_activities.example.json` 是活度配置模板。后续填入每个标准源在测量时刻的 Bq 后，可以扩展 `calibration.json` 的 `efficiency_coefficients`，活度列就会自动计算。

## GitHub 构建

初始化并上传：

```bash
cd /Users/Zhuanz/gamma-spectrum-analyzer
git init
git add .
git commit -m "Initial gamma spectrum analyzer"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

推送后，GitHub Actions 会运行 `.github/workflows/build.yml`：

- Windows: 上传 `gamma-spectra-windows.zip`，里面包含 `gamma-spectra.exe` 和 `gamma-spectra-gui.exe`
- macOS: 上传 `gamma-spectra-macos.dmg`

如果要让我直接推到 GitHub，需要先在 Codex 里连接 GitHub 插件或提供已配置好的本地 git remote/token。
