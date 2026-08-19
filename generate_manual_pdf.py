from __future__ import annotations

import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
import os

def register_chinese_font():
    candidates = [
        '/System/Library/Fonts/Supplemental/Songti.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        'C:\\Windows\\Fonts\\simsun.ttc',
        'C:\\Windows\\Fonts\\msyh.ttc',
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont('Chinese', p))
                return True
            except Exception:
                continue
    return False

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return  # Skip cover page
        self.saveState()
        self.setFont('Chinese', 8.5)
        self.setFillColor(colors.HexColor('#718096'))
        
        # Header
        self.drawString(20*mm, 285*mm, 'γ 能谱识别与放射性核素分析软件 (v0.2.0) - 用户使用说明书')
        self.setStrokeColor(colors.HexColor('#CBD5E0'))
        self.setLineWidth(0.5)
        self.line(20*mm, 282*mm, 190*mm, 282*mm)
        
        # Footer
        self.setLineWidth(0.5)
        self.line(20*mm, 15*mm, 190*mm, 15*mm)
        page_text = f'第 {self._pageNumber} 页 / 共 {page_count} 页'
        self.drawRightString(190*mm, 10*mm, page_text)
        self.drawString(20*mm, 10*mm, '高纯锗 (HPGe) 伽马能谱智能分析系统')
        self.restoreState()

def build_pdf(filename='γ能谱识别与放射性核素分析软件_使用说明书.pdf'):
    if not register_chinese_font():
        raise RuntimeError("No Chinese font found on system!")

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )

    c_title = ParagraphStyle(
        'CoverTitle',
        fontName='Chinese',
        fontSize=24,
        leading=32,
        textColor=colors.HexColor('#1A365D'),
        alignment=1,
        spaceAfter=15,
    )
    c_sub = ParagraphStyle(
        'CoverSub',
        fontName='Chinese',
        fontSize=13,
        leading=18,
        textColor=colors.HexColor('#4A5568'),
        alignment=1,
        spaceAfter=25,
    )
    c_meta = ParagraphStyle(
        'CoverMeta',
        fontName='Chinese',
        fontSize=10,
        leading=16,
        textColor=colors.HexColor('#4A5568'),
        alignment=1,
    )
    
    h1 = ParagraphStyle(
        'H1',
        fontName='Chinese',
        fontSize=15,
        leading=20,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )
    h2 = ParagraphStyle(
        'H2',
        fontName='Chinese',
        fontSize=11.5,
        leading=16,
        textColor=colors.HexColor('#2D3748'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True,
    )
    body = ParagraphStyle(
        'Body',
        fontName='Chinese',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=5,
    )
    bullet = ParagraphStyle(
        'Bullet',
        fontName='Chinese',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=10,
        spaceAfter=3,
    )
    code = ParagraphStyle(
        'Code',
        fontName='Chinese',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#1A202C'),
        backColor=colors.HexColor('#F7FAFC'),
        borderColor=colors.HexColor('#E2E8F0'),
        borderWidth=0.5,
        borderPadding=5,
        spaceAfter=5,
    )
    tbl_cell = ParagraphStyle(
        'TblCell',
        fontName='Chinese',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#2D3748'),
    )
    tbl_hdr = ParagraphStyle(
        'TblHdr',
        fontName='Chinese',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
        alignment=1,
    )

    story = []

    # ==================== COVER ====================
    story.append(Spacer(1, 35*mm))
    story.append(Paragraph('γ 能谱识别与放射性核素分析系统', c_title))
    story.append(Paragraph('用户使用与操作指南说明书 (v0.2.0)', c_sub))
    story.append(HRFlowable(width='60%', thickness=1.5, color=colors.HexColor('#3182CE'), spaceAfter=25*mm))
    
    meta_info = '''
    <b>系统类型：</b>高纯锗 (HPGe) 伽马能谱智能分析软件<br/>
    <b>遵循标准：</b>GB/T 11713-2015 / GB/T 11743-2013<br/>
    <b>适用任务：</b>核素智能定性识别 · 效率刻度拟合 · 镭钍钾比活度定量分析<br/>
    <b>支持平台：</b>Windows 10/11 (x64) · macOS (Apple Silicon / Intel)
    '''
    story.append(Paragraph(meta_info, c_meta))
    story.append(PageBreak())

    # ==================== CHAPTER 1 ====================
    story.append(Paragraph('第一章 软件系统概述', h1))
    story.append(Paragraph('<b>γ 能谱识别与放射性核素分析软件</b> 是一套专为核物理测量、环境辐射监测及核分析赛道打造的高性能谱学数据处理与分析软件。系统基于高纯锗（HPGe）半导体探测器采集的多道能谱数据，深度集成了谱线预处理、自适应能量刻度、SNIP 连续本底扣除、多峰非线性拟合、核素定性识别库匹配以及基于国家标准的镭钍钾比活度定量分析等核心功能。', body))
    
    story.append(Paragraph('1.1 核心功能特性', h2))
    story.append(Paragraph('• <b>全自动能量刻度与自适应增益匹配：</b> 内置自适应两步刻度引擎，能自动识别标准源模式（~0.297 keV/ch）与测试样模式（~0.280 keV/ch），实现无感智能能量校准。', bullet))
    story.append(Paragraph('• <b>精准连续本底扣除与 ROI 积分：</b> 采用统计自适应 SNIP 算法扣除复杂康普顿散射台阶，ROI 窗口基于峰底全宽精确积分，彻底消除低能弱峰高估问题。', bullet))
    story.append(Paragraph('• <b>国际标准统计不确定度传递：</b> 严格遵循 ISO 11929 / Currie 误差传递公式，精准计算净峰面积相对标准不确定度（Area Uncert%）。', bullet))
    story.append(Paragraph('• <b>镭钍钾比活度国家标准定量（GB/T 11743-2013）：</b> 内置 7NTR-1024 效率曲线与样品质量自动关联，一键完成 Ra-226、Th-232、K-40 定量计算。', bullet))
    story.append(Paragraph('• <b>跨平台双模支持：</b> 提供友好的 PyQt6 图形交互界面（GUI）与高效的命令行工具（CLI），支持全自动化批量分析与图表报表导出。', bullet))

    # ==================== CHAPTER 2 ====================
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('第二章 运行与安装指南', h1))
    
    story.append(Paragraph('2.1 免安装独立可执行程序直接运行（推荐）', h2))
    story.append(Paragraph('从 GitHub Releases 页面下载最新构建的独立运行资产包：', body))
    story.append(Paragraph('• <b>Windows 平台：</b> 下载并解压 <code>gamma-spectra-windows.zip</code>，双击 <code>gamma-spectra-gui.exe</code> 即可启动图形界面，或在终端中直接调用 <code>gamma-spectra.exe</code> 命令行程序。', bullet))
    story.append(Paragraph('• <b>macOS 平台：</b> 下载 <code>gamma-spectra-macos.dmg</code>，挂载后拖入 Applications 应用程序目录即可直接使用。', bullet))

    story.append(Paragraph('2.2 Python 源码环境运行', h2))
    story.append(Paragraph('适用于二次开发或定制算法研究：', body))
    py_code = '''# 1. 克隆仓库并安装依赖
git clone https://github.com/MCGAgain/Test.git
cd Test
python -m venv .venv
# 激活虚拟环境 (Windows: .\\.venv\\Scripts\\Activate.ps1 | macOS: source .venv/bin/activate)
pip install -e .

# 2. 启动 GUI 或 CLI
gamma-spectra-gui
gamma-spectra analyze ".\\核分析赛道\\核素识别\\标准源\\Cs-137+I-131\\I-131 Cs-137 水样1.xls"'''
    story.append(Paragraph(py_code.replace('\n', '<br/>').replace(' ', '&nbsp;'), code))

    story.append(PageBreak())

    # ==================== CHAPTER 3 ====================
    story.append(Paragraph('第三章 GUI 图形界面操作指南', h1))
    
    story.append(Paragraph('3.1 界面布局说明', h2))
    story.append(Paragraph('GUI 主界面由 <b>顶部工具栏</b>、<b>中央交互式谱图区</b> 和 <b>底部状态显示栏</b> 组成：', body))
    story.append(Paragraph('1. <b>顶部工具栏：</b> 包含「导入谱」、「分析」、「峰信息」、「保存CSV」、「镭钍钾分析」及谱线视图切换单选按钮（能量 / 道号坐标、线性 / 对数 Y 轴）。', bullet))
    story.append(Paragraph('2. <b>中央谱图区：</b> 高清展示实测能谱曲线，识别出的核素特征峰将以垂直标记并在峰顶标注核素名称与射线能量。支持鼠标框选局部放大与滚轮缩放。', bullet))
    story.append(Paragraph('3. <b>底部状态栏：</b> 实时显示鼠标十字光标所在处的道号（Channel）、能量（Energy/keV）及计数（Counts）。', bullet))

    story.append(Paragraph('3.2 任务一：核素定性识别与峰信息查看', h2))
    story.append(Paragraph('<b>标准操作步骤：</b>', body))
    story.append(Paragraph('1. 点击 <b>「导入谱」</b>，在文件对话框中选择待分析的 <code>.xls</code> 谱数据文件（如 <code>I-131 Cs-137 水样1.xls</code> 或 <code>测试样1.xls</code>）。', bullet))
    story.append(Paragraph('2. 软件自动执行智能自适应能量刻度并重绘全谱。', bullet))
    story.append(Paragraph('3. 点击 <b>「分析」</b> 按钮，系统自动弹出 <b>「峰信息」</b> 数据表格。', bullet))
    story.append(Paragraph('4. （可选）点击峰信息窗口右下角 <b>「保存」</b> 按钮，可将完整的峰参数表格导出为标准 CSV 文件。', bullet))

    story.append(Paragraph('<b>峰信息表格各列物理量详细说明：</b>', body))
    
    tbl_data = [
        [Paragraph('<b>列名</b>', tbl_hdr), Paragraph('<b>物理含义说明</b>', tbl_hdr), Paragraph('<b>计算依据 / 算法说明</b>', tbl_hdr)],
        [Paragraph('Channel', tbl_cell), Paragraph('特征峰中心道址', tbl_cell), Paragraph('高斯非线性拟合中心通道 μ', tbl_cell)],
        [Paragraph('ROI L / ROI R', tbl_cell), Paragraph('峰感兴趣区左右边界', tbl_cell), Paragraph('以峰中心 ±1.60×FWHM 确定的积分边界', tbl_cell)],
        [Paragraph('Energy(KeV)', tbl_cell), Paragraph('特征γ射线实测能量', tbl_cell), Paragraph('经能量刻度方程 E = a0 + a1·CH 计算', tbl_cell)],
        [Paragraph('FWTM(E) / FWHM(E)', tbl_cell), Paragraph('峰十分之一 / 半高全宽', tbl_cell), Paragraph('FWTM=4.292σ, FWHM=2.355σ (keV)', tbl_cell)],
        [Paragraph('ROI Area', tbl_cell), Paragraph('扣除连续谱本底后特征毛面积', tbl_cell), Paragraph('SNIP 扣大康普顿台阶后在 ROI 区间的面积', tbl_cell)],
        [Paragraph('Net Area', tbl_cell), Paragraph('净峰面积', tbl_cell), Paragraph('ROI 区间内扣除两端点梯形本底后的净计数', tbl_cell)],
        [Paragraph('Area Uncert(%)', tbl_cell), Paragraph('净面积相对统计不确定度', tbl_cell), Paragraph('Currie 方差传递公式 100%·σ(N)/N', tbl_cell)],
        [Paragraph('Nuclide', tbl_cell), Paragraph('识别确认的放射性核素', tbl_cell), Paragraph('比对特征γ衰变数据库确认的核素名称', tbl_cell)],
        [Paragraph('Yield(%)', tbl_cell), Paragraph('特征γ射线分支比/发射几率', tbl_cell), Paragraph('核数据库标准发射几率', tbl_cell)],
        [Paragraph('Efficiency', tbl_cell), Paragraph('探测器全能峰探测效率', tbl_cell), Paragraph('能量-效率曲线 ln(ε)=∑a_i·ln(E)^i 计算', tbl_cell)],
        [Paragraph('Activity(Bq)', tbl_cell), Paragraph('核素活度定量结果', tbl_cell), Paragraph('A = Net Area / (t_live · Yield · Efficiency)', tbl_cell)],
        [Paragraph('Activity Uncert(%)', tbl_cell), Paragraph('活度合成相对标准不确定度', tbl_cell), Paragraph('面积统计误差与探测效率不确定度合成', tbl_cell)],
        [Paragraph('Count rate', tbl_cell), Paragraph('ROI 计数率 (cps)', tbl_cell), Paragraph('ROI Area / 活时间 (Live Time)', tbl_cell)],
    ]
    
    t = Table(tbl_data, colWidths=[28*mm, 58*mm, 84*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2B6CB0')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#F7FAFC'), colors.white]),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t)

    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('3.3 任务二：土壤样品镭钍钾比活度定量分析', h2))
    story.append(Paragraph('<b>操作流程：</b>', body))
    story.append(Paragraph('1. 点击 <b>「导入谱」</b>，选择土壤测试样（如 <code>镭钍钾1.xls</code> 至 <code>镭钍钾5.xls</code>）。', bullet))
    story.append(Paragraph('2. 点击工具栏 <b>「镭钍钾分析」</b> 按钮。', bullet))
    story.append(Paragraph('3. 系统自动加载内置 7NTR-1024 效率曲线与标准样品装样质量，直接弹出定量分析结果对话框，清晰呈现 Ra-226、Th-232、K-40 各核素的实测活度（Bq）及比活度（Bq/kg）。', bullet))

    story.append(PageBreak())

    # ==================== CHAPTER 4 ====================
    story.append(Paragraph('第四章 CLI 命令行工具与批量自动化分析', h1))
    story.append(Paragraph('软件提供强大的命令行工具 <code>gamma-spectra</code>，适用于自动化批处理、脚本集成与持续验证。', body))

    story.append(Paragraph('4.1 CLI 子命令一览', h2))
    story.append(Paragraph('• <code>gamma-spectra analyze &lt;spectrum.xls&gt; [--csv out.csv] [--plot out.png]</code>：执行全谱定性定量分析并导出报表。', bullet))
    story.append(Paragraph('• <code>gamma-spectra rtk &lt;soil.xls&gt; [--mass-kg 0.334]</code>：快速计算土壤样品中镭钍钾比活度。', bullet))
    story.append(Paragraph('• <code>gamma-spectra calibrate &lt;spec.xls&gt;</code>：拟合输出能谱的能量刻度二次多项式系数。', bullet))

    story.append(Paragraph('4.2 常用自动化批处理脚本示例', h2))
    story.append(Paragraph('<b>PowerShell 批量分析测试样：</b>', body))
    ps_cmd = '''1..5 | ForEach-Object {
    .\\gamma-spectra.exe analyze ".\\核分析赛道\\核素识别\\测试样\\测试样$_\\测试样$_.xls" `
        --csv "output\\test$_.csv" --plot "output\\test$_.png"
}'''
    story.append(Paragraph(ps_cmd.replace('\n', '<br/>').replace(' ', '&nbsp;'), code))

    story.append(Paragraph('<b>PowerShell 批量计算 5 个土壤样品的镭钍钾比活度：</b>', body))
    ps_rtk = '''1..5 | ForEach-Object {
    .\\gamma-spectra.exe rtk ".\\核分析赛道\\镭钍钾定量分析\\测试样品数据\\镭钍钾$_.xls"
}'''
    story.append(Paragraph(ps_rtk.replace('\n', '<br/>').replace(' ', '&nbsp;'), code))

    # ==================== CHAPTER 5 ====================
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('第五章 核心算法与物理模型说明', h1))
    
    story.append(Paragraph('5.1 统计自适应 SNIP 连续本底扣除', h2))
    story.append(Paragraph('连续散射谱本底（如低能处的康普顿台阶与多重散射连续谱）采用统计自适应连续峰剪切（SNIP）算法进行估计，经过多次迭代平滑抑制高频噪声，精准提取纯净特征峰信号。', body))

    story.append(Paragraph('5.2 净峰面积不确定度方差传递（ISO 11929 / Currie）', h2))
    story.append(Paragraph('净峰面积采用梯形端点本底扣除法：N = G_raw - (n / 2m)·(B_L + B_R)。根据独立泊松计数统计方差合成定律：', body))
    story.append(Paragraph('• 净峰面积方差：Var(N) = G_raw + (n / 2m)^2 · (B_L + B_R)<br/>• 相对不确定度：Area Uncert(%) = 100% · sqrt(Var(N)) / N', code))
    story.append(Paragraph('该模型能真实反映不同信噪比下的物理测量涨落：对于高计数主峰（如 Cs-137 661 keV），不确定度小于 1%；对于坐落在巨大康普顿台阶上的低能弱峰（如 I-131 284 keV），不确定度自然呈现在 30%~40% 之间，完全符合高纯锗谱仪测量规律。', body))

    story.append(Paragraph('5.3 能量-效率校准对数多项式模型', h2))
    story.append(Paragraph('高纯锗探测效率曲线采用国家标准推荐的对数多项式进行全能峰效率拟合：ln(ε) = ∑ a_i · [ln(E)]^i。内置土壤校准源 7NTR-1024 效率曲线在 50 keV ~ 2000 keV 全能区拟合优度 R^2 > 0.999，确保镭钍钾比活度分析相对偏差小于 1.5%。', body))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f'Successfully generated {filename}')

if __name__ == '__main__':
    build_pdf('γ能谱识别与放射性核素分析软件_使用说明书.pdf')
