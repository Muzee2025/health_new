#!/usr/bin/env python
"""Render publication-style application figures from the registered local data."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA_DEFAULT = ROOT / "docs" / "plan" / "ai-application" / "figures-sci"
SKILL = Path(r"C:\Users\14012\.agents\skills\math-modeling")
PYDEPS = ROOT / "tmp" / "ai-application-20261027" / "pydeps"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=QA_DEFAULT, help="PNG/SVG/PDF output folder")
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(ROOT / "tmp" / "ai-application-20261027" / "mpl-cache")
    sys.path.insert(0, str(PYDEPS))
    sys.path.insert(0, str(SKILL / "tools" / "figure" / "scripts"))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle
    from matplotlib.text import Text
    from PIL import Image
    from visual_qa import audit_layout

    def read_csv(path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    chart = read_csv(ROOT / "docs" / "plan" / "ai-application" / "chart-data.csv")
    regional = read_csv(ROOT / "docs" / "plan" / "ai-application" / "revision-20261027" / "regional-education-2024.csv")
    literature = json.loads((ROOT / "docs" / "plan" / "ai-application" / "sci-revision-20261027" / "literature-data.json").read_text(encoding="utf-8"))
    css = (ROOT / "src" / "styles" / "tokens.css").read_text(encoding="utf-8")

    def token(name: str) -> str:
        match = re.search(r"--" + re.escape(name) + r":\s*(#[\da-fA-F]{6})", css)
        if not match:
            raise ValueError(f"Missing registered design token: {name}")
        return match.group(1)

    C = {
        "purple": token("brand-500"), "purple_dark": token("brand-700"),
        "apricot": token("accent-apricot"), "sage": token("accent-sage"),
        "pale": token("brand-50"), "warm": token("surface-warm"),
        "ink": token("gray-800"), "muted": token("gray-600"),
        "grid": token("gray-200"), "white": token("gray-0"),
    }
    plt.rcParams.update({
        "font.family": "SimSun", "font.sans-serif": ["SimSun", "Arial"],
        "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 8.5,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
        "text.color": C["ink"], "axes.labelcolor": C["ink"],
        "xtick.color": C["ink"], "ytick.color": C["ink"],
        "axes.edgecolor": C["ink"], "axes.linewidth": .65,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.unicode_minus": False, "svg.fonttype": "none", "pdf.fonttype": 42,
        "ps.fonttype": 42, "savefig.facecolor": "white", "figure.facecolor": "white",
        "axes.facecolor": "white", "lines.linewidth": .75,
    })

    specs: list[dict] = []
    audits: list[dict] = []
    emitted: list[dict] = []

    def finish(fig, n: int, stem: str, caption: str, panels: list[dict], units: str,
               chart_type: str, grayscale: str, notes: str = "") -> None:
        # Matplotlib's global fallback selects Arial for a whole string on this
        # runtime. Assign a CJK face to Chinese labels and Arial to Latin-only text.
        fig.canvas.draw()
        for artist in fig.findobj(match=Text):
            value = artist.get_text()
            has_cjk = any("\u3400" <= ch <= "\u9fff" for ch in value)
            artist.set_fontfamily("SimSun" if has_cjk else "Arial")
        issues = audit_layout(fig)
        audits.append({"figure": stem, "issues": [list(x) for x in issues]})
        for ext, kwargs in (("svg", {}), ("pdf", {"metadata": {"Title": caption}}),
                            ("png", {"dpi": 600, "pil_kwargs": {"optimize": True, "compress_level": 9}})):
            path = out / f"{stem}.{ext}"
            fig.savefig(path, format=ext, bbox_inches=None, **kwargs)
            if ext == "svg":
                path.write_text("\n".join(line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())+"\n",encoding="utf-8")
            if ext == "png":
                with Image.open(path) as im:
                    indexed = im.convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                          dither=Image.Dither.NONE)
                    indexed.save(path, format="PNG", optimize=True, compress_level=9, dpi=(600, 600))
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError(f"{path.name} exceeds 2 MiB")
            emitted.append({"file": path.name, "bytes": path.stat().st_size, "format": ext,
                            **({"mode": "indexed-256"} if ext == "png" else {})})
        specs.append({
            "number": n, "id": stem, "caption_zh": caption, "panels": panels,
            "units": units, "chart_type": chart_type,
            "grayscale_readability": grayscale,
            "external_caption_notes": notes,
            "size_in": [5.7087, round(float(fig.get_figheight()), 3)],
            "visualSource": "src/styles/tokens.css",
            "license": "Original project rendering; numerical facts attributed to cited primary sources; publisher figures not copied",
            "sourceFiles": ["sci-revision-20261027/literature-data.json"] if n in [12,13] else
                ["revision-20261027/regional-education-2024.csv"] if n in [10,11,14] else
                ["chart-data.csv"] if n in [1,2,3,4,9] else ["Original project concept and current engineering records"],
            "outputs": {ext: f"../figures-sci/{stem}.{ext}" for ext in ("svg", "pdf", "png")},
        })
        plt.close(fig)

    def setup_axes(ax, grid_axis="x"):
        ax.spines["left"].set_linewidth(.65)
        ax.spines["bottom"].set_linewidth(.65)
        ax.tick_params(width=.6, length=2.5, pad=2.5)
        ax.grid(axis=grid_axis, color=C["grid"], linewidth=.55, zorder=0)
        ax.set_axisbelow(True)

    def panel_label(ax, label):
        ax.text(-.11, 1.04, label, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=9, fontweight="bold", color=C["ink"], clip_on=False)

    def rows(group):
        return [r for r in chart if r["group"] == group]

    # 01: only exact reported point estimates; the <5% group is intentionally absent.
    fig, axs = plt.subplots(1, 2, figsize=(5.7087, 2.65))
    fig.subplots_adjust(left=.13, right=.985, bottom=.23, top=.91, wspace=.36)
    vals = [20.2, 45.4]
    axs[0].bar([0, 1], vals, width=.55, color=[C["sage"], C["purple"]], edgecolor=C["ink"], linewidth=.65, zorder=3)
    axs[0].set(xticks=[0, 1], xticklabels=["轻度风险", "高风险"], ylim=(0, 55), ylabel="样本内比例（%）")
    for x, v in enumerate(vals): axs[0].text(x, v + 1.2, f"{v:.1f}", ha="center", va="bottom", fontsize=8)  # noqa: E701
    setup_axes(axs[0]); panel_label(axs[0], "a")  # noqa: E702
    groups = ["不做或抄作业", "考试作弊"]
    ax = axs[1]; x = [0, 1]; w = .33  # noqa: E702
    ax.bar([i-w/2 for i in x], [4, 3.5], width=w, color=C["sage"], edgecolor=C["ink"], linewidth=.65, label="无风险组", zorder=3)
    ax.bar([i+w/2 for i in x], [17.1, 14], width=w, color=C["purple"], edgecolor=C["ink"], linewidth=.65, hatch="///", label="高风险组", zorder=3)
    ax.set(xticks=x, xticklabels=groups, ylim=(0, 22))
    for xp, v in zip([i-w/2 for i in x], [4, 3.5]): ax.text(xp, v+.45, f"{v:g}", ha="center", fontsize=8)  # noqa: B905, E701
    for xp, v in zip([i+w/2 for i in x], [17.1, 14]): ax.text(xp, v+.45, f"{v:g}", ha="center", fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y", color=C["grid"], linewidth=.55); panel_label(ax, "b")  # noqa: E702
    ax.legend(frameon=False, loc="upper right", handlelength=1.2, borderaxespad=.1)
    finish(fig, 1, "fig01-youth", "青少年筛查风险组的上学意愿与自陈学习行为", [
        {"panel": "a", "meaning": "轻度与高风险组经常或每天不想上学的比例", "y_unit": "%"},
        {"panel": "b", "meaning": "无风险与高风险组自陈不做/抄作业及考试作弊比例", "y_unit": "%"}], "%", "分组柱状图（并列）",
        "绿色与紫色明度不同；面板b另以斜线纹理编码高风险组。", "仅绘制报道的精确百分比；<5%的无风险组不画柱、不推算点值。相关性比较，不作诊断或因果解释。")

    # 02: horizontal bars are a compact comparison of distinct survey items.
    pressure = rows("大学生竞争感知")
    fig, ax = plt.subplots(figsize=(5.7087, 2.35)); fig.subplots_adjust(left=.30, right=.96, bottom=.24, top=.95)  # noqa: E702
    labels = [r["indicator"] for r in pressure]; values = [float(r["value"]) for r in pressure]  # noqa: E702
    yy = list(range(len(labels)))
    ax.barh(yy, values, height=.54, color=C["purple"], edgecolor=C["ink"], linewidth=.65, zorder=3)
    ax.set(yticks=yy, yticklabels=labels, xlim=(0, 105), xlabel="受访者认同比例（%）")
    ax.invert_yaxis()
    for y, v in zip(yy, values): ax.text(v+1, y, f"{v:.1f}", va="center", fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y", visible=False)  # noqa: E702
    finish(fig, 2, "fig02-pressure", "大学生对学业竞争的感知", [{"panel": "a", "meaning": "四项学业竞争感知题项的报告比例", "x_unit": "%"}], "%", "水平柱状图",
           "单色柱配合数值标签，灰度打印仍可比较柱长。", "四项为不同问项，不相加；不是焦虑或抑郁症状/诊断率。")

    # 03: independent reported totals, no uncertainty intervals are available.
    edu = rows("教育体量")
    fig, ax = plt.subplots(figsize=(5.7087, 2.2)); fig.subplots_adjust(left=.27, right=.96, bottom=.25, top=.94)  # noqa: E702
    labels = [r["indicator"] for r in edu]; values = [float(r["value"]) for r in edu]  # noqa: E702
    yy = list(range(len(labels)))
    ax.barh(yy, values, height=.5, color=[C["purple"], C["apricot"], C["sage"]], edgecolor=C["ink"], linewidth=.65, zorder=3)
    ax.set(yticks=yy, yticklabels=labels, xlim=(0, 6600), xlabel="在校生（万人）")
    ax.invert_yaxis()
    for y, v in zip(yy, values): ax.text(v+75, y, f"{v:,.2f}", va="center", fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y", visible=False)  # noqa: E702
    finish(fig, 3, "fig03-education", "全国普通本专科、普通高中及初中在校生规模", [{"panel": "a", "meaning": "三个教育学段报告在校生总量", "x_unit": "万人"}], "万人", "水平柱状图",
           "三种色相与直接数值标签共同区分学段。", "按教育统计原学段口径；没有报告置信区间，不添加区间。")

    # 04: differently scoped procurements are separated and never averaged.
    fig, axs = plt.subplots(1, 2, figsize=(5.7087, 2.55))
    fig.subplots_adjust(left=.18, right=.98, bottom=.25, top=.91, wspace=.78)
    ax = axs[0]; yy=[0,1]; vals=[11.47,45]  # noqa: E702
    ax.barh(yy, vals, height=.5, color=[C["sage"], C["purple"]], edgecolor=C["ink"], linewidth=.65, zorder=3)
    ax.set(yticks=yy, yticklabels=["单项软件", "综合系统"], xlim=(0,55), xlabel="公告金额（万元）"); ax.invert_yaxis()  # noqa: E702
    for y,v in zip(yy,vals): ax.text(v+1,y,f"{v:g}",va="center",fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y",visible=False); panel_label(ax,"a")  # noqa: E702
    ax = axs[1]; ax.set_xlim(0,125); ax.set_ylim(-.55,2.25); ax.set_yticks([0,1], ["龙泉驿两包", "成都教科院"]); ax.invert_yaxis(); ax.set_xlabel("公告金额（万元）")  # noqa: E702
    ax.barh(0,40.7,height=.48,color=C["purple"],edgecolor=C["ink"],linewidth=.65,zorder=3)
    ax.barh(0,24.6,left=40.7,height=.48,color=C["apricot"],edgecolor=C["ink"],linewidth=.65,hatch="///",zorder=3)
    ax.barh(1,96.5,height=.48,color=C["sage"],edgecolor=C["ink"],linewidth=.65,zorder=3)
    ax.text(20.35,0,"40.7",ha="center",va="center",fontsize=8,color="white")
    ax.text(53,0,"24.6",ha="center",va="center",fontsize=8,color=C["ink"])
    ax.text(99,1,"96.5",va="center",fontsize=8)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=C["purple"],edgecolor=C["ink"],label="测评包"), Patch(facecolor=C["apricot"],edgecolor=C["ink"],hatch="///",label="干预包"), Patch(facecolor=C["sage"],edgecolor=C["ink"],label="区域服务")],
              frameon=False,loc="lower right",fontsize=8,handlelength=1.2,borderaxespad=.1)
    setup_axes(ax); ax.grid(axis="y",visible=False); panel_label(ax,"b")  # noqa: E702
    finish(fig, 4, "fig04-procurement", "公开采购案例的标的金额与交付范围", [
        {"panel":"a","meaning":"高校单项软件与综合系统公告金额","x_unit":"万元"},
        {"panel":"b","meaning":"龙泉驿测评及干预分包金额与成都区域服务金额","x_unit":"万元"}], "万元", "分面水平条形图；区域测评/干预采用堆叠",
        "面板b使用色相和干预斜线纹理；各金额均有数值标签。", "四项采购的标的和服务周期不同，不计算均价，不代表本项目报价。")

    # Concept diagrams use only thin, square-corner boxes and arrows.
    def concept_canvas(height):
        fig, ax = plt.subplots(figsize=(5.7087, height)); fig.subplots_adjust(left=.035,right=.965,bottom=.07,top=.94)  # noqa: E702
        ax.set(xlim=(0,1),ylim=(0,1)); ax.axis("off"); return fig,ax  # noqa: E702
    def box(ax,x,y,w,h,text,fill="white",linestyle="-"):
        ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor=C[fill],edgecolor=C["purple_dark"],linewidth=.7,linestyle=linestyle))
        ax.text(x,y,text,ha="center",va="center",fontsize=8.3,linespacing=1.25,color=C["ink"])
    def arrow(ax,p,q,style="-"):
        ax.add_patch(FancyArrowPatch(p,q,arrowstyle="-|>",mutation_scale=7,linewidth=.65,color=C["muted"],linestyle=style,shrinkA=1,shrinkB=1))

    fig,ax=concept_canvas(2.95)
    nodes=[(.25,.76,"青少年与高校压力\n学习适应与支持需要"),(.75,.76,"心理测评与持续观察\n记录与阶段变化"),(.75,.25,"统计分析与模型摘要\n已确认事实与审核资料"),(.25,.25,"人工复核与持续支持\n答复、预约与跟进")]
    for x,y,t in nodes:
        box(ax,x,y,.39,.26,t,fill="warm")
    for p,q in [((.45,.76),(.55,.76)),((.75,.62),(.75,.39)),((.55,.25),(.45,.25))]:arrow(ax,p,q)  # noqa: E701
    finish(fig,5,"fig05-mindmap","AI+校园心理测评与持续支持逻辑",[
        {"panel":"a","meaning":"由左上经右上、右下到左下的四步工作顺序"}],"不适用","四区顺序逻辑图","细线方框与顺序箭头；不依赖颜色识别方向。","概念框描述项目构想，不代表功能已经实现或效果已经验证。")

    fig,ax=concept_canvas(2.8)
    layers=[(.82,"业务工作区｜Vue 3","测评记录 · 留言预约 · 教师复核",False),(.59,"授权接口与现有数据层","身份角色 · 显式师生分配 · SQLite",False),(.36,"拟增强的数据分析","质量检查 · 描述统计 · 同口径趋势",True),(.13,"可选检索与大模型模块","审核知识 · 结构校验 · 人工复核",True)]
    for y,h1,h2,dashed in layers:
        box(ax,.5,y,.83,.155,h1+"\n"+h2,fill="pale" if not dashed else "warm",linestyle="--" if dashed else "-")
    for y1,y2 in [(.735,.675),(.505,.445),(.275,.215)]: arrow(ax,(.5,y1),(.5,y2))  # noqa: E701
    finish(fig,6,"fig06-architecture","系统业务、数据与拟增强AI模块的层级关系",[
        {"panel":"a","meaning":"既有原型层与拟增强/可选能力的边界"}],"不适用","分层架构示意图","实线框表示既有原型范围，虚线框表示拟增强或可选能力；文字和线型双重编码。","图中技术状态依据当前仓库记录；虚线能力未表示已部署或已完成模型评测。")

    fig,ax=concept_canvas(2.8)
    nodes=[(.17,.76,"知情与授权\n任务和角色核对"),(.50,.76,"最少必要字段\n质量检查与统计"),(.83,.76,"审核知识检索\n获批模型调用"),(.83,.42,"来源与结构校验\n失败分母留存"),(.50,.42,"授权人员复核\n修订与确认"),(.17,.42,"学生说明支持\n答复与持续跟进")]
    for x,y,t in nodes: box(ax,x,y,.255,.18,t,fill="pale",linestyle="--")  # noqa: E701
    for p,q in [((.30,.76),(.37,.76)),((.63,.76),(.70,.76)),((.83,.66),(.83,.52)),((.70,.42),(.63,.42)),((.37,.42),(.30,.42))]: arrow(ax,p,q)  # noqa: E701
    box(ax,.5,.12,.82,.13,"无资料 / 超时 / 结构错误 → 明示不可判断 → 人工渠道",fill="warm",linestyle="--")
    arrow(ax,(.83,.32),(.83,.20),"--")
    finish(fig,7,"fig07-ai-workflow","受控AI分析与大模型协作的人机工作流",[
        {"panel":"a","meaning":"授权、数据检查、模型校验和人工支持的顺序"}],"不适用","流程图","连续主流程用实线箭头；异常回退用虚线。", "拟建设的人机协作流程；模型输出不自动形成诊断或现实处置。")

    # 09: two distinct questions from the same report; no conversion or ratio.
    service = rows("大学生免费心理咨询")
    fig,ax=plt.subplots(figsize=(5.7087,1.9)); fig.subplots_adjust(left=.33,right=.96,bottom=.29,top=.94)  # noqa: E702
    labels=[r["indicator"] for r in service]; vals=[float(r["value"]) for r in service]; yy=[0,1]  # noqa: E702
    ax.barh(yy,vals,height=.46,color=[C["purple"],C["sage"]],edgecolor=C["ink"],linewidth=.65,zorder=3)
    ax.set(yticks=yy,yticklabels=labels,xlim=(0,100),xlabel="报告比例（%）"); ax.invert_yaxis()  # noqa: E702
    for y,v in zip(yy,vals): ax.text(v+1,y,f"{v:.1f}",va="center",fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y",visible=False)  # noqa: E702
    finish(fig,9,"fig09-service","大学生对校内免费心理咨询的知晓与使用报告",[
        {"panel":"a","meaning":"知晓学校提供免费咨询的报告比例", "x_unit":"%"},
        {"panel":"b","meaning":"曾使用学校免费咨询的报告比例", "x_unit":"%"}],"%","水平柱状图（两项独立报告）",
        "两条柱采用不同明度的紫/绿；直接标注数值。","两项问项分别报告；不把知晓率转换为使用率，也不推断服务质量或总体使用分布。")

    def bachelor_total(r):
        return int(r["academic_bachelor_students"]) + int(r["vocational_normal_short_students"])
    ranked=sorted(regional,key=bachelor_total,reverse=True)[:12]
    labels=[r["region"] for r in ranked]; vals=[bachelor_total(r)/10000 for r in ranked]  # noqa: E702
    fig,ax=plt.subplots(figsize=(5.7087,3.55)); fig.subplots_adjust(left=.18,right=.96,bottom=.18,top=.98)  # noqa: E702
    yy=list(range(len(labels))); bars=ax.barh(yy,vals,height=.62,color=C["purple"],edgecolor=C["ink"],linewidth=.6,zorder=3)  # noqa: E702
    bars[0].set_color(C["sage"])
    ax.set(yticks=yy,yticklabels=labels,xlim=(0,max(vals)*1.16),xlabel="普通、职业本专科在校生（万人）"); ax.invert_yaxis()  # noqa: E702
    for y,v in zip(yy,vals): ax.text(v+max(vals)*.012,y,f"{v:.1f}",va="center",fontsize=8)  # noqa: B905, E701
    setup_axes(ax); ax.grid(axis="y",visible=False)  # noqa: E702
    finish(fig,10,"fig10-regional-college","2024年普通本专科在校生规模居前的12个地区",[
        {"panel":"a","meaning":"31个省级地区中普通本科与职业本专科在校生合计前12位", "x_unit":"万人"}],"万人","按值排序的水平条形图",
        "首位用灰绿色强调，其余同色；标签与排序支持灰度阅读。","合计由普通本科在校生与职业本专科在校生相加；只显示前12位。")

    neighbors={"湖北","河南","安徽","江西","湖南","重庆","陕西"}
    region_rows=[r for r in regional if r["region"] in neighbors]
    region_rows.sort(key=lambda r: ["湖北","河南","安徽","江西","湖南","重庆","陕西"].index(r["region"]))
    labels=[r["region"] for r in region_rows]
    bachelor=[int(r["normal_vocational_undergraduates"])/10000 for r in region_rows]
    senior=[int(r["regular_senior_students"])/10000 for r in region_rows]
    junior=[int(r["junior_students"])/10000 for r in region_rows]
    fig,axs=plt.subplots(1,3,figsize=(5.7087,3.15),sharey=True,sharex=True)
    fig.subplots_adjust(left=.14,right=.99,bottom=.25,top=.9,wspace=.43)
    common_max=max(bachelor+senior+junior)*1.27
    for ax,values,title,color,letter in zip(axs,[bachelor,senior,junior],["普通本专科","普通高中","初中"],[C["purple"],C["apricot"],C["sage"]],["a","b","c"]):  # noqa: B007, B905
        yy=list(range(len(labels))); ax.barh(yy,values,height=.52,color=color,edgecolor=C["ink"],linewidth=.6,zorder=3)  # noqa: E702
        ax.set(yticks=yy,yticklabels=labels,xlim=(0,common_max),xticks=[0,200,400,600],title=None)
        ax.set_xlabel("万人",labelpad=3)
        for y,v in zip(yy,values): ax.text(v+max(values)*.025,y,f"{v:.0f}",va="center",fontsize=8)  # noqa: B905, E701
        setup_axes(ax); ax.grid(axis="y",visible=False); panel_label(ax,letter)  # noqa: E702
    axs[0].invert_yaxis()
    finish(fig,11,"fig11-hubei-neighbours","湖北及相邻地区2024年学生规模对照",[
        {"panel":"a","meaning":"普通本专科在校生", "x_unit":"万人"},
        {"panel":"b","meaning":"普通高中在校生", "x_unit":"万人"},
        {"panel":"c","meaning":"初中在校生", "x_unit":"万人"}],"万人","三面板分组水平条形图",
        "各教育学段使用相同横轴范围与刻度，不同token色相和直接数值标签。","地区包含湖北与六个相邻省级地区；各面板量纲和横轴范围相同。")

    # 12: pooled estimates and reported 95% CIs from one systematic review.
    stages=literature["study"]["education_stage_subgroups"]
    stage_labels={"Primary school":"小学","Middle school":"初中","High school":"高中","Undergraduate school":"本科阶段"}
    fig,ax=plt.subplots(figsize=(5.7087,2.35)); fig.subplots_adjust(left=.26,right=.91,bottom=.25,top=.94)  # noqa: E702
    yy=list(range(len(stages)))
    for y,r in zip(yy,stages):  # noqa: B905
        est=float(r["estimate_percent"]); lo=float(r["ci95_lower_percent"]); hi=float(r["ci95_upper_percent"])  # noqa: E702
        ax.errorbar(est,y,xerr=[[est-lo],[hi-est]],fmt="o",markersize=4.1,color=C["purple_dark"],
                    ecolor=C["muted"],elinewidth=.75,capsize=2,capthick=.75,zorder=3)
        ax.text(37.2,y,f"k={r['studies_k']}",ha="left",va="center",fontsize=8,color=C["ink"])
    ax.set(yticks=yy,yticklabels=[stage_labels[r["stage"]] for r in stages],xlim=(0,42),
           xticks=[0,10,20,30,40],xlabel="抑郁症状筛查阳性合并比例（%）")
    ax.invert_yaxis(); setup_axes(ax); ax.grid(axis="y",visible=False)  # noqa: E702
    finish(fig,12,"fig12-literature-stage","中国儿童青少年抑郁症状筛查阳性率的学段亚组Meta分析结果",[
        {"panel":"a","meaning":"同一系统综述按教育阶段报告的合并比例与原报95%置信区间；右侧k为研究数","x_unit":"%"}],"%（95%置信区间）","水平森林图",
        "统一实心圆点、细置信区间线与端帽；灰度下依靠位置和形状可辨。",
        "来源：Zhou等2024年系统综述与Meta分析。k为纳入研究数；学段样本与研究可重叠，不将各组n/k相加。筛查阳性不是临床诊断率。")

    # 13: preserve the education CSV's mainland-region order; exclude Hong Kong and Taiwan.
    english_to_cn={"Anhui":"安徽","Beijing":"北京","Tianjin":"天津","Chongqing":"重庆","Fujian":"福建","Gansu":"甘肃",
        "Guangdong":"广东","Guangxi":"广西","Guizhou":"贵州","Hainan":"海南","Hebei":"河北",
        "Heilongjiang":"黑龙江","Henan":"河南","Hubei":"湖北","Hunan":"湖南","Jiangsu":"江苏",
        "Jiangxi":"江西","Jilin":"吉林","Liaoning":"辽宁","Inner Mongolia":"内蒙古","Ningxia":"宁夏",
        "Qinghai":"青海","Shaanxi":"陕西","Shandong":"山东","Shanghai":"上海","Shanxi":"山西",
        "Sichuan":"四川","Xinjiang":"新疆","Tibet":"西藏","Yunnan":"云南","Zhejiang":"浙江"}
    geographic=literature["geographic_subgroups"]["rows"]
    geo_by_cn={english_to_cn[r["region"]]:r for r in geographic if r["region"] in english_to_cn}
    geo=[geo_by_cn[r["region"]] for r in regional]
    if len(geo)!=31: raise ValueError("Literature geography must map to all 31 mainland education regions")  # noqa: E701
    fig=plt.figure(figsize=(5.7087,4.65)); gs=fig.add_gridspec(1,5,width_ratios=[10,.7,2.1,10,.7],wspace=.03)  # noqa: E702
    fig.subplots_adjust(left=.12,right=.99,bottom=.14,top=.96)
    for row,subset,label in [(0,geo[:16],"a"),(1,geo[16:],"b")]:
        col=0 if row==0 else 3
        ax=fig.add_subplot(gs[0,col]); kax=fig.add_subplot(gs[0,col+1],sharey=ax); yy=list(range(len(subset)))  # noqa: E702
        for y,r in zip(yy,subset):  # noqa: B905
            est=float(r["estimate_percent"]); lo=float(r["ci95_lower_percent"]); hi=float(r["ci95_upper_percent"])  # noqa: E702
            single=int(r["studies_k"])==1
            ax.errorbar(est,y,xerr=[[est-lo],[hi-est]],fmt="o",markersize=4.0,
                markerfacecolor="white" if single else C["purple"],markeredgecolor=C["purple_dark"],markeredgewidth=.8,
                ecolor=C["muted"],elinewidth=.65,capsize=1.8,capthick=.65,zorder=3)
            kax.text(.5,y,str(r["studies_k"]),ha="center",va="center",fontsize=8,color=C["ink"])
        ax.set(yticks=yy,yticklabels=[english_to_cn[r["region"]] for r in subset],xlim=(0,100),xticks=[0,25,50,75,100])
        ax.invert_yaxis(); setup_axes(ax); ax.grid(axis="y",visible=False)  # noqa: E702
        ax.text(.01,1.01,label,transform=ax.transAxes,ha="left",va="bottom",fontsize=9,fontweight="bold",color=C["ink"],clip_on=False)
        kax.set_ylim(ax.get_ylim()); kax.set_xlim(0,1); kax.axis("off")  # noqa: E702
        kax.text(.5,1.01,"k",transform=kax.transAxes,ha="center",va="bottom",fontsize=8,color=C["ink"])
    fig.axes[0].set_xlabel("合并比例（%）"); fig.axes[2].set_xlabel("合并比例（%）")  # noqa: E702
    finish(fig,13,"fig13-literature-regions","中国大陆省级地区儿童青少年抑郁症状筛查合并比例",[
        {"panel":"a","meaning":"依2024年教育统计顺序排列的前16个大陆省级地区；空心点表示k=1","x_unit":"%（95%置信区间）"},
        {"panel":"b","meaning":"同序排列的其余15个大陆省级地区；空心点表示k=1","x_unit":"%（95%置信区间）"}],
        "%（95%置信区间）；右侧k为研究数","双面板水平森林图（31省级地区；16/15分面）",
        "x轴两面板共用0–100%范围；k=1以空心圆表示并在侧栏标研究数。",
        "来源：同一系统综述补充表S2；仅含大陆31省级地区，按教育统计CSV原序而非效应值排序。该图汇总纳入研究，不是省级人口风险地图；研究/样本可重叠。")

    # 14: each province contributes equally to the Lorenz curve's horizontal share.
    stage_fields=[("普通本专科","normal_vocational_undergraduates",C["purple"],"-","o"),
        ("普通高中","regular_senior_students",C["apricot"],"--","s"),("初中","junior_students",C["sage"],"-.","^")]
    fig,ax=plt.subplots(figsize=(5.7087,3.25)); fig.subplots_adjust(left=.16,right=.97,bottom=.21,top=.96)  # noqa: E702
    ax.plot([0,100],[0,100],color=C["muted"],linestyle=(0,(3,2)),linewidth=.7,label="完全平等线",zorder=1)
    region_share=[100*i/len(regional) for i in range(len(regional)+1)]
    for title,field,color,linestyle,marker in stage_fields:
        values=sorted(int(r[field]) for r in regional); total=sum(values); cumulative=[0]  # noqa: E702
        for value in values: cumulative.append(cumulative[-1]+value)  # noqa: E701
        shares=[100*v/total for v in cumulative]
        ax.plot(region_share,shares,color=color,linestyle=linestyle,linewidth=.8,marker=marker,
                markersize=3.6,markerfacecolor="white",markeredgewidth=.7,markevery=4,label=title,zorder=3)
    ax.set(xlim=(0,100),ylim=(0,100),xticks=[0,20,40,60,80,100],yticks=[0,20,40,60,80,100],
           xlabel="省级地区累计占比（%）",ylabel="在校生累计占比（%）")
    setup_axes(ax,grid_axis="both"); ax.legend(frameon=False,loc="upper left",ncol=2,handlelength=2.0,columnspacing=1.1)  # noqa: E702
    finish(fig,14,"fig14-education-lorenz","2024年31个省级地区分学段在校生规模的Lorenz曲线",[
        {"panel":"a","meaning":"各省级地区按本学段在校生数升序排列后的累计地区份额与累计在校生份额","x_unit":"%","y_unit":"%"}],
        "%（横轴为省级地区份额；纵轴为在校生份额）","Lorenz曲线（本专科、普通高中、初中）",
        "灰色虚线为平等线；三学段使用不同token色相、线型和标记形状。",
        "每个省级地区在横轴等权；每条曲线按对应学段地区值独立排序。该图描述31地区分布，不表示个体或校级差异。")

    report={"figures":len(specs),"audits":audits,"files":emitted,
            "png_total_bytes":sum(x["bytes"] for x in emitted if x["format"]=="png"),
            "all_layout_audits_clear":all(not a["issues"] for a in audits),
            "target_width_mm":145,"dpi_png":600,"png_palette":"indexed color, up to 256 colors",
            "max_file_bytes":2*1024*1024,"font_policy":["Arial","SimSun"],
            "source_data":{"chart":"docs/plan/ai-application/chart-data.csv","regional":"docs/plan/ai-application/revision-20261027/regional-education-2024.csv","literature":"docs/plan/ai-application/sci-revision-20261027/literature-data.json","palette":"src/styles/tokens.css"}}
    (out/"figure-layout-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    spec_path=ROOT/"docs"/"plan"/"ai-application"/"sci-revision-20261027"/"figure-spec.json"
    spec_path.parent.mkdir(parents=True,exist_ok=True)
    spec_path.write_text(json.dumps({"owner":"A","version":"1.0","status":"rendered-review","updated":"2026-10-27","figures":specs},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if not report["all_layout_audits_clear"]:
        print(json.dumps({"figures":len(specs),"layout_issues":[a for a in audits if a["issues"]]},ensure_ascii=False))
        return 2
    print(json.dumps({"figures":len(specs),"files":len(emitted),"max_bytes":max(x["bytes"] for x in emitted),"layout_issues":0,"out":str(out)},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
