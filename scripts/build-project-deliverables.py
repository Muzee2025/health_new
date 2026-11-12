#!/usr/bin/env python3
"""Build editable project application DOCX and defense PPTX from approved sources.

Run with the bundled document Python for DOCX, or ppt-skills Python for PPTX:
  python scripts/build-project-deliverables.py --stage docx
  python scripts/build-project-deliverables.py --stage pptx
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil  # noqa: F401
import sys  # noqa: F401
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_MD = ROOT / "docs/plan/心域智链申报计划书.md"
TEMPLATE = Path(r"C:\University\Files\附件.docx")
DOCX_OUT = ROOT / "deliverables/心域智链项目申报材料.docx"
PPTX_OUT = ROOT / "deliverables/心域智链项目答辩稿.pptx"


def overview_text() -> str:
    return (
        "心域智链面向校园心理支持协作，围绕学生自助信息、教师按明确分配处理、过程留痕与校方运维验证，"
        "建设Vue、FastAPI与SQLite形态的本地工程原型。项目已有认证、权限、素材库、登录与性能等隔离验证记录；"
        "新增问答、预警事件、跟进和单生导出待本轮整合验收。项目不提供诊断或治疗；真实模型、试点、责任、预算、"
        "人员资格及生产Linux/TLS条件均待校内确认。计划先定义边界，再完成隔离评测与恢复验证，经批准后决定是否小范围试点。"
    )


def replace_cell(cell, value: str, size_pt: float = 9.5, bold: bool = False) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = 0
    p.paragraph_format.space_before = 0
    run = p.add_run(value)
    run.font.name = "宋体"
    run._element.rPr.rFonts.set("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", "宋体")
    run.font.size = __import__("docx").shared.Pt(size_pt)
    run.bold = bold


def set_cell_once(table, row: int, col: int, value: str, size_pt: float = 9.5) -> None:
    replace_cell(table.cell(row, col), value, size_pt)


def set_table_borders_and_spacing(table) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    for row in table.rows:
        row_props = row._tr.get_or_add_trPr()
        if row_props.find(qn("w:cantSplit")) is None:
            row_props.append(OxmlElement("w:cantSplit"))
        for cell in row.cells:
            tc_mar = cell._tc.get_or_add_tcPr().find(qn("w:tcMar"))
            if tc_mar is None:
                tc_mar = OxmlElement("w:tcMar")
                cell._tc.get_or_add_tcPr().append(tc_mar)
            for edge in ("top", "start", "bottom", "end"):
                el = tc_mar.find(qn(f"w:{edge}"))
                if el is None:
                    el = OxmlElement(f"w:{edge}")
                    tc_mar.append(el)
                el.set(qn("w:w"), "90")
                el.set(qn("w:type"), "dxa")
            for p in cell.paragraphs:
                p.paragraph_format.space_after = 0
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        item = borders.find(qn(f"w:{edge}"))
        if item is None:
            item = OxmlElement(f"w:{edge}")
            borders.append(item)
        item.set(qn("w:val"), "single")
        item.set(qn("w:sz"), "4")
        item.set(qn("w:space"), "0")
        item.set(qn("w:color"), "D9D9D9")


def application_summary() -> str:
    return (
        "本项目面向高校心理支持协作，建设学生入口、教师授权工作区和过程记录工具，支持学生了解测评、科普、"
        "留言、预约与AI对话等不同路径，教师仅在明确分配范围内核实信息和记录跟进。现有原型采用Vue、FastAPI与SQLite，"
        "具备认证、权限及隔离验证记录；本轮新增问答、预警事件、跟进和个体导出待整合验收。项目不进行疾病诊断或治疗，"
        "不代替专业人员。真实模型评测、校内试点、团队资格、周期、预算和生产部署均待确认。"
    )


def build_docx() -> None:
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f"Retained template not found: {TEMPLATE}")
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    source = PLAN_MD.read_text(encoding="utf-8")
    doc = Document(str(TEMPLATE))
    if len(doc.tables) != 3:
        raise RuntimeError(f"Expected 3 source tables, got {len(doc.tables)}")

    # Attachment 1: preserve template geometry, leave real persons and approvals blank.
    app = doc.tables[0]
    set_cell_once(app, 0, 1, "心域智链校园心理支持协作平台", 10)
    set_cell_once(app, 1, 1, "项目来源待确认；各选项暂不勾选。", 9)
    for row in range(3, 8):
        for col in (1, 2, 4, 6, 8):
            set_cell_once(app, row, col, "【待填写】", 8.5)
    # Adviser rows contain name, unit, title and phone.
    for row in (9, 10):
        for col in (1, 3, 5, 7):
            set_cell_once(app, row, col, "【待填写】", 8.5)
    set_cell_once(
        app,
        11,
        1,
        "资格条件尚未核验：竞赛获奖/项目立项选项均不勾选。请提供与上一年度要求匹配的证明材料；无证明时按学校规定处理。",
        9,
    )
    set_cell_once(app, 12, 1, application_summary(), 9)
    # Keep the college-review and review-group signing rows empty and untouched.
    set_table_borders_and_spacing(app)

    # Attachment 2: variable budget and cycle, with a compliant 100–300 character overview.
    brief = doc.tables[1]
    set_cell_once(brief, 0, 1, "心域智链校园心理支持协作平台", 10)
    set_cell_once(brief, 1, 1, "金额待测算；暂不填报。", 10)
    set_cell_once(brief, 2, 1, "【待填写】", 9)
    set_cell_once(brief, 2, 3, "【待填写】", 9)
    set_cell_once(brief, 4, 0, application_summary(), 9.5)
    set_table_borders_and_spacing(brief)

    # Appendix 3 cover: retain the Wuhan College mark and populate only safe known facts.
    cover = doc.tables[2]
    values = [
        "心域智链校园心理支持协作平台",
        "【待填写】",
        "【待填写】",
        "武汉学院（申报主体待确认）",
        "【待填写】",
        "【待填写】",
        "【待填写】",
    ]
    for i, value in enumerate(values):
        set_cell_once(cover, i, 2, value, 10)

    # Keep the original plan title, remove template instructions after it, then add source content.
    title_para = next((p for p in doc.paragraphs if p.text.strip() == "项 目 计 划 书"), None)
    if title_para is None:
        raise RuntimeError("Could not locate the Appendix 3 plan title slot")
    title_para.text = "项 目 计 划 书"
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    body = doc.element.body
    found = False
    for child in list(body):
        if found and child.tag != qn("w:sectPr"):
            body.remove(child)
        if child is title_para._p:
            found = True
    if not found:
        raise RuntimeError("Plan title is not attached to the document body")

    # Convert the plan Markdown's six sections and appendices into editable Word blocks.
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## 一、"))
    content_lines = lines[start:]
    i = 0
    while i < len(content_lines):
        line = content_lines[i].rstrip()
        if not line.strip() or line.startswith(">"):
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            code_lines = []
            while i < len(content_lines) and not content_lines[i].startswith("```"):
                code_lines.append(content_lines[i])
                i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.25)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run("\n".join(code_lines))
            run.font.name = "Consolas"
            run.font.size = Pt(9)
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(content_lines) and content_lines[i].strip().startswith("|"):
                row = [c.strip() for c in content_lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c or "-") for c in row):
                    rows.append(row)
                i += 1
            if not rows:
                continue
            cols = max(len(r) for r in rows)
            table = doc.add_table(rows=0, cols=cols)
            table.style = "Normal Table"
            for ri, raw in enumerate(rows):
                cells = table.add_row().cells
                for ci in range(cols):
                    value = raw[ci] if ci < len(raw) else ""
                    replace_cell(cells[ci], re.sub(r"\*\*(.*?)\*\*", r"\1", value), 9.0, bold=(ri == 0))
                    cells[ci].vertical_alignment = 1
                    if ri == 0:
                        tc_pr = cells[ci]._tc.get_or_add_tcPr()
                        shd = OxmlElement("w:shd")
                        shd.set(qn("w:fill"), "EEE7F2")
                        tc_pr.append(shd)
                if ri == 0:
                    tr_pr = table.rows[0]._tr.get_or_add_trPr()
                    repeat = OxmlElement("w:tblHeader")
                    repeat.set(qn("w:val"), "true")
                    tr_pr.append(repeat)
            set_table_borders_and_spacing(table)
            doc.add_paragraph().paragraph_format.space_after = Pt(1)
            continue
        if line.startswith("#### ") or line.startswith("### ") or line.startswith("## "):
            level = 1 if line.startswith("## ") else (2 if line.startswith("### ") else 3)
            heading = re.sub(r"^#{2,4}\s+", "", line)
            p = doc.add_paragraph()
            p.paragraph_format.keep_with_next = True
            p.paragraph_format.space_before = Pt(10 if level == 1 else 6)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(heading)
            run.bold = True
            run.font.name = "宋体"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
            run.font.size = Pt(14 if level == 1 else (12 if level == 2 else 11.5))
            i += 1
            continue
        if line.startswith("---"):
            i += 1
            continue
        text = line
        if text.startswith("- "):
            text = "• " + text[2:]
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1（\2）", text)
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.22
        p.paragraph_format.keep_together = True
        if re.match(r"^\d+\.\s", text):
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(text)
        run.font.name = "宋体"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
        run.font.size = Pt(12)
        i += 1

    # Normalize paragraph and table font behavior while preserving template page setup and mark.
    for p in doc.paragraphs:
        for run in p.runs:
            if run.font.size is None:
                run.font.size = Pt(10.5)
            if run.font.name is None:
                run.font.name = "宋体"
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    DOCX_OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(DOCX_OUT))
    print(f"DOCX={DOCX_OUT}")


def load_design_tokens() -> dict[str, str]:
    """Resolve the deck palette from the project's registered CSS token source."""
    css = (ROOT / "src/styles/tokens.css").read_text(encoding="utf-8")
    raw = dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9A-Fa-f]{6}|var\(--[\w-]+\))\s*;", css))

    def resolve(name: str, trail: tuple[str, ...] = ()) -> str:
        if name in trail or name not in raw:
            raise ValueError(f"Missing or cyclic design token: --{name}")
        value = raw[name]
        if value.startswith("var("):
            return resolve(value[6:-1], trail + (name,))
        return value.upper()

    mapping = {
        "paper": "surface-warm", "white": "gray-0", "brand": "brand-600", "brand_dark": "brand-700",
        "brand_soft": "brand-100", "apricot": "accent-apricot", "apricot_soft": "accent-apricot-soft",
        "sage": "accent-sage", "sage_soft": "accent-sage-soft", "rose_soft": "accent-rose-soft",
        "ink": "text-primary", "muted": "text-secondary", "grid": "border",
        "danger": "danger", "warning": "warning", "success": "success", "info": "info",
    }
    return {out: resolve(token) for out, token in mapping.items()}


def load_approved_logo() -> Path:
    manifest = json.loads((ROOT / "src/assets/manifest.json").read_text(encoding="utf-8"))
    item = next((asset for asset in manifest["assets"] if asset.get("id") == "brand-logo-vertical-512-png"), None)
    if not item or item.get("status") != "approved":
        raise RuntimeError("The selected brand logo is missing from the manifest or is not approved")
    path = ROOT / "src/assets" / item["path"]
    if not path.is_file():
        raise FileNotFoundError(f"Approved brand logo missing: {path}")
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != item.get("sha256"):
        raise RuntimeError("Approved brand logo hash does not match the asset manifest")
    print(f"Visual source: src/styles/tokens.css; logo={item['path']} status=approved sha256={actual_hash}")
    return path


PALETTE = load_design_tokens()


def build_pptx() -> None:
    try:
        from pptx import Presentation as InspectPresentation  # noqa: I001
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR  # noqa: F401
        from pptx.util import Inches, Pt  # noqa: F401
        from pptx_designer import Presentation, validate_resolved_theme
        from pptx_designer.renderer.theme import ThemeComposer
        from pptx_designer.tools.text import text
        from pptx_designer.tools.shapes import rect, rrect, arrow, oval
        from pptx_designer.tools.images import cover_image
    except Exception as exc:
        raise RuntimeError("PPTX build requires the dedicated ppt-skills runtime with pptx-designer") from exc

    theme = ThemeComposer().compose(
        style="storytelling-driven", palette="mental-health-app", fonts="chinese-simplified",
        decoration="accent-bar", layout="standard", mood="warm human companionship", seed=2026,
    )
    # The project token file is the active visual source; adapt the complete resolved theme to it.
    theme["name"] = "心域智链相伴品牌-2026-10-22"
    theme["colors"].update({
        "primary": PALETTE["brand"], "on-primary": PALETTE["white"], "secondary": PALETTE["sage"],
        "accent": PALETTE["apricot"], "background": PALETTE["paper"], "foreground": PALETTE["ink"],
        "muted": PALETTE["brand_soft"], "muted-foreground": PALETTE["muted"],
        "border": PALETTE["grid"], "destructive": PALETTE["danger"],
    })
    theme["semantic_roles"].update({
        "background": PALETTE["paper"], "surface": PALETTE["white"], "ink": PALETTE["ink"],
        "muted": PALETTE["muted"], "accent": PALETTE["apricot"], "accent-secondary": PALETTE["sage"],
        "success": PALETTE["success"], "warning": PALETTE["warning"], "danger": PALETTE["danger"],
        "border": PALETTE["grid"], "data-series-1": PALETTE["brand"], "data-series-2": PALETTE["sage"],
    })
    theme["typography"] = {"heading": "Microsoft YaHei", "body": "Microsoft YaHei"}
    validate_resolved_theme(theme)
    prs = Presentation(theme=theme, strict_theme=True)
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    I = Inches  # noqa: E741, F841
    W, H = 13.333, 7.5
    FONT = "Microsoft YaHei"
    logo = load_approved_logo()

    def slide_base(num: int, section: str, title: str, subtitle: str = ""):
        s = prs.slides.add_slide(prs.slide_layouts[6])
        rect(s, 0, 0, W, H, PALETTE["paper"])
        rect(s, 0.62, 0.52, 0.055, 0.32, PALETTE["apricot"])
        text(s, 0.82, 0.45, 2.6, 0.26, section.upper(), 10.5, PALETTE["brand"], True, font_name=FONT)
        text(s, 0.82, 0.77, 11.7, 0.56, title, 27, PALETTE["ink"], True, font_name=FONT)
        if subtitle:
            text(s, 0.84, 1.34, 11.35, 0.38, subtitle, 13.3, PALETTE["muted"], font_name=FONT)
        rect(s, 0.72, 7.0, 11.9, 0.012, PALETTE["grid"])
        text(s, 0.78, 7.08, 10.3, 0.2, "心域智链｜待业务确认的申报稿｜工程原型，不作诊疗服务承诺", 9.2, PALETTE["muted"], font_name=FONT)
        text(s, 12.12, 7.05, 0.4, 0.25, f"{num:02d}", 10, PALETTE["brand"], True, align="right", font_name=FONT)
        return s

    def note(slide, content: str):
        slide.notes_slide.notes_text_frame.text = content

    def pill(s, x, y, w, label, color=None, fill=None):
        rrect(s, x, y, w, 0.34, fill or PALETTE["brand_soft"], line=color or PALETTE["brand_soft"])
        text(s, x + 0.08, y + 0.05, w - 0.16, 0.23, label, 11, color or PALETTE["brand"], True, align="center", font_name=FONT)

    def step(s, x, y, w, number, heading, body, fill):
        oval(s, x, y, 0.4, 0.4, fill, line=fill)
        text(s, x, y + 0.045, 0.4, 0.28, str(number), 13, PALETTE["white"], True, align="center", font_name=FONT)
        text(s, x, y + 0.53, w, 0.36, heading, 16.5, PALETTE["ink"], True, font_name=FONT)
        text(s, x, y + 0.96, w, 0.9, body, 13, PALETTE["muted"], font_name=FONT)

    # 1. Cover: use the approved logo mark as a focal point, with editable text.
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, W, H, PALETTE["paper"])
    rect(s, 0, 0, 0.2, H, PALETTE["brand"])
    cover_image(s, 9.25, 1.15, 2.6, 2.65, str(logo))
    text(s, 0.95, 0.92, 6.2, 0.32, "武汉学院｜项目申报与答辩", 13, PALETTE["brand"], True, font_name=FONT)
    text(s, 0.95, 1.66, 7.8, 1.3, "心域智链", 38, PALETTE["ink"], True, font_name=FONT)
    text(s, 0.98, 2.85, 7.8, 0.72, "校园心理支持协作平台", 24, PALETTE["brand"], True, font_name=FONT)
    text(s, 0.98, 3.82, 7.3, 0.95, "让学生更清楚地找到支持，让教师在授权范围内跟进记录。", 18, PALETTE["muted"], font_name=FONT)
    pill(s, 0.98, 5.36, 2.85, "待业务确认的申报稿", PALETTE["brand"], PALETTE["brand_soft"])
    text(s, 0.98, 6.0, 6.5, 0.34, "团队、周期、预算与试点条件均待确认", 12.5, PALETTE["muted"], font_name=FONT)
    text(s, 0.98, 7.08, 10.6, 0.2, "心域智链｜本地工程原型｜不构成诊断、治疗或上线承诺", 9.2, PALETTE["muted"], font_name=FONT)
    note(s, "各位评审老师好，我们汇报的是心域智链校园心理支持协作平台。今天希望先对项目边界、校内责任和验证条件达成共识，再决定是否进入隔离评测和试点筹备。当前稿件中的团队、周期、预算与校内试点信息仍待业务确认。")

    # 2. Product scope.
    s = slide_base(2, "01 项目定位", "一个支持协作的工程原型", "当前目标是把入口、权限、记录和复验准备放在同一条协作链中。")
    rrect(s, 0.95, 2.02, 4.6, 3.56, PALETTE["brand_soft"], line=PALETTE["brand_soft"])
    text(s, 1.3, 2.4, 3.9, 0.42, "支持协作", 24, PALETTE["brand"], True, font_name=FONT)
    text(s, 1.3, 3.06, 3.85, 1.65, "学生入口\n教师授权工作区\n受控记录与评测准备", 17, PALETTE["ink"], font_name=FONT)
    rect(s, 6.1, 2.04, 0.025, 3.55, PALETTE["apricot"])
    text(s, 6.55, 2.1, 5.7, 0.38, "明确服务边界", 18, PALETTE["ink"], True, font_name=FONT)
    for j, line in enumerate(["AI不进行疾病诊断或治疗", "测评与模型输出需标明来源并经人工核实", "系统不替代校内人工服务或紧急流程", "模型未配置时保留非AI路径"]):
        oval(s, 6.58, 2.75 + j * 0.62, 0.18, 0.18, PALETTE["sage"], line=PALETTE["sage"])
        text(s, 6.93, 2.69 + j * 0.62, 5.2, 0.32, line, 15, PALETTE["muted"], font_name=FONT)
    note(s, "我们把项目定位为校园心理支持协作的软件原型。AI只提供一般信息支持和路径提示，不作诊断、治疗或危机处置决定。最终服务范围由学校业务负责人和专业人员确认。")

    # 3. Stakeholder value.
    s = slide_base(3, "02 使用者与价值", "三方价值分别验证", "目前没有试点成效数据；先确定每类用户的任务和证据。")
    blocks = [
        (0.92, "学生", "找到自助信息、留言或预约入口\n看懂记录状态和可见范围", "验证：任务完成、卡点、理解度", PALETTE["brand_soft"], PALETTE["brand"]),
        (4.88, "教师/服务人员", "在明确分配范围内核实信息\n记录原因、处理和后续动作", "验证：任务用时、记录一致性", PALETTE["sage_soft"], PALETTE["sage"]),
        (8.84, "采购与治理校方", "审查权限、部署、备份、成本\n决定责任与分期验收", "验证：证据完备、恢复演练", PALETTE["apricot_soft"], PALETTE["brand"]),
    ]
    for x, title, body, metric, fill, accent in blocks:
        rrect(s, x, 2.18, 3.56, 3.4, fill, line=fill)
        text(s, x + 0.26, 2.52, 3.0, 0.42, title, 18.5, accent, True, font_name=FONT)
        text(s, x + 0.26, 3.15, 3.0, 1.08, body, 14.2, PALETTE["ink"], font_name=FONT)
        rect(s, x + 0.26, 4.55, 2.85, 0.02, PALETTE["white"])
        text(s, x + 0.26, 4.76, 3.0, 0.5, metric, 12, PALETTE["muted"], font_name=FONT)
    note(s, "学生侧重能否快速理解支持方式，教师侧重是否能在授权范围内完成工作，学校侧重治理和持续运行条件。任务完成率、处理耗时和使用反馈都要在批准的试点中采集，当前没有可报的效果数字。")

    # 4. Existing engineering base.
    s = slide_base(4, "03 当前事实", "已有本地工程底座，生产条件仍未完成", "下列技术事实来自仓库与本地隔离验证记录，不代表校级生产部署。")
    cols = [(1.0, "Vue", "学生端与教师端界面", PALETTE["brand_soft"]), (4.75, "FastAPI", "认证、业务路由与权限检查", PALETTE["sage_soft"]), (8.5, "SQLite", "当前本地运行副本", PALETTE["apricot_soft"])]
    for x, head, body, fill in cols:
        rrect(s, x, 2.35, 3.05, 1.4, fill, line=fill)
        text(s, x + 0.2, 2.64, 2.65, 0.34, head, 19, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, x + 0.2, 3.1, 2.65, 0.45, body, 13, PALETTE["muted"], align="center", font_name=FONT)
    for x in (4.12, 7.87):
        arrow(s, x, 2.82, 0.42, 0.32, PALETTE["apricot"], line=PALETTE["apricot"])
    rrect(s, 1.0, 4.28, 10.55, 1.05, PALETTE["white"], line=PALETTE["grid"])
    text(s, 1.28, 4.48, 9.95, 0.58, "已验证：认证/权限、登录、本地运行与前端加载等隔离记录。性能证据：冷登录JS gzip 755,644→140,577字节（仅JS响应体）。", 14.2, PALETTE["ink"], font_name=FONT)
    pill(s, 1.05, 5.73, 2.45, "生产Linux/TLS待完成", PALETTE["warning"], PALETTE["apricot_soft"])
    pill(s, 3.72, 5.73, 2.7, "真实模型未配置/评测", PALETTE["warning"], PALETTE["apricot_soft"])
    pill(s, 6.65, 5.73, 2.72, "校方业务责任待确认", PALETTE["warning"], PALETTE["apricot_soft"])
    note(s, "仓库和本地记录显示，前端使用Vue、后端使用FastAPI，当前本地运行副本使用SQLite。性能数字仅是登录页面请求的JS gzip响应体，不是总资源或加载时长。生产Linux与TLS、真实模型配置、身份集成和学校运维条件没有完成。")

    # 5. Student path.
    s = slide_base(5, "04 学生侧流程", "学生入口区分四种支持路径", "任务分流清楚，学生才知道信息来自哪里、下一步由谁承接。")
    step(s, 0.95, 2.25, 2.55, 1, "自助了解", "测评或科普\n说明来源和适用边界", PALETTE["brand"])
    step(s, 3.9, 2.25, 2.55, 2, "向教师留言", "进入求助/问答\n具体回复流程待验收", PALETTE["sage"])
    step(s, 6.85, 2.25, 2.55, 3, "AI对话", "一般支持和信息提示\n模型服务尚未配置", PALETTE["apricot"])
    step(s, 9.8, 2.25, 2.55, 4, "预约", "查看真实时段\n按学校规则办理", PALETTE["brand"])
    for x in (3.53, 6.48, 9.43):
        arrow(s, x, 2.3, 0.27, 0.2, PALETTE["grid"], line=PALETTE["grid"])
    rrect(s, 1.05, 5.4, 10.95, 0.75, PALETTE["white"], line=PALETTE["grid"])
    text(s, 1.3, 5.6, 10.45, 0.32, "需要校方确定：服务时间、响应责任、告知与退出方式、测评来源/授权", 13.7, PALETTE["muted"], font_name=FONT)
    note(s, "学生入口把自助内容、留言、AI对话和预约分开。AI对话不会假扮真人，教师留言是否承诺回复时限取决于校内责任安排。测评来源和适用人群也需要专业核验。")

    # 6. Teacher path.
    s = slide_base(6, "05 教师侧流程", "教师处置建立在明确分配与持久记录上", "本轮正在补齐问答、预警事件、跟进和单生导出；状态为待Lead整合验收。")
    flow = [(1.0, "分配范围", "操作员显式维护"), (3.85, "核实线索", "人工审阅来源"), (6.7, "记录结论", "保存理由与责任"), (9.55, "跟进/导出", "单生授权范围")]
    for i, (x, title, body) in enumerate(flow, 1):
        rrect(s, x, 2.55, 2.4, 1.5, PALETTE["white"], line=PALETTE["grid"])
        text(s, x + 0.17, 2.78, 2.08, 0.36, title, 16.5, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, x + 0.14, 3.3, 2.12, 0.4, body, 12.4, PALETTE["muted"], align="center", font_name=FONT)
        if i < 4:
            arrow(s, x + 2.48, 3.12, 0.3, 0.2, PALETTE["apricot"], line=PALETTE["apricot"])
    rrect(s, 1.0, 4.7, 5.15, 0.95, PALETTE["sage_soft"], line=PALETTE["sage_soft"])
    text(s, 1.25, 4.93, 4.65, 0.46, "权限原则：教师只看操作员分配给自己的学生", 13.2, PALETTE["ink"], True, font_name=FONT)
    rrect(s, 6.5, 4.7, 5.15, 0.95, PALETTE["apricot_soft"], line=PALETTE["apricot_soft"])
    text(s, 6.75, 4.93, 4.65, 0.46, "验收原则：刷新后能核对结论、原因、处理人", 13.2, PALETTE["ink"], True, font_name=FONT)
    note(s, "教师的学生范围来自操作员维护的分配关系，辅导员文本字段不作为权限。系统拟把预警核实、结论、跟进和单生导出串起来。本轮新功能还要等待Lead完成整合验收；如果未通过，必须在最终材料中保留待完成状态。")

    # 7. Governance and data boundary.
    s = slide_base(7, "06 权限与数据", "数据边界先于界面承诺", "访问由服务端权限决定；按钮显隐不能替代授权检查。")
    zones = [(0.95, 2.2, 3.3, "学生本人", "本人账号\n本人允许查看的记录", PALETTE["brand_soft"], PALETTE["brand"]),
             (5.0, 2.2, 3.3, "明确分配教师", "仅看被显式分配的学生\n按角色执行授权接口", PALETTE["sage_soft"], PALETTE["sage"]),
             (9.05, 2.2, 3.3, "校内操作与治理", "维护分配、账号和责任\n明确审计与恢复流程", PALETTE["apricot_soft"], PALETTE["brand"])]
    for x, y, w, title, body, fill, color in zones:
        rrect(s, x, y, w, 2.05, fill, line=fill)
        text(s, x + 0.2, y + 0.28, w - 0.4, 0.36, title, 16.4, color, True, align="center", font_name=FONT)
        text(s, x + 0.24, y + 0.85, w - 0.48, 0.78, body, 13.3, PALETTE["ink"], align="center", font_name=FONT)
    rect(s, 4.53, 3.15, 0.35, 0.03, PALETTE["brand"])
    rect(s, 8.58, 3.15, 0.35, 0.03, PALETTE["brand"])
    rrect(s, 1.18, 4.9, 10.9, 0.92, PALETTE["white"], line=PALETTE["grid"])
    text(s, 1.48, 5.11, 10.3, 0.46, "真实业务数据按权限读取；评测和演示使用合成数据；外部模型传输须先完成审查与告知。", 14, PALETTE["ink"], font_name=FONT)
    note(s, "权限审计需要检查服务端行为。真实业务数据由后端授权接口读取，评测演示使用合成数据。匿名显示不代表平台无法关联账号；外部模型是否传输信息、传输哪些字段以及保存多久，都要经学校审核。")

    # 8. Five-platform benchmark.
    s = slide_base(8, "07 外部参照", "五个平台公开资料提供有限的导航参照", "公开门户与官方帮助文档可比较入口组织；本次未登录实测，也不比较服务效果。")
    platforms = [
        ("青海大学", "公开预约流程", "服务说明与预约步骤分开", PALETTE["brand_soft"]),
        ("壹心理", "官网门户", "咨询、测评、问答等分入口", PALETTE["sage_soft"]),
        ("简单心理", "官网门户", "区分咨询、课程与测评", PALETTE["apricot_soft"]),
        ("Togetherall", "官方帮助", "资源、课程、评估与记录", PALETTE["brand_soft"]),
        ("SimplePractice", "官方帮助", "日程、预约请求与档案分区", PALETTE["sage_soft"]),
    ]
    for i, (name, kind, lesson, fill) in enumerate(platforms):
        x = 0.84 + i * 2.45
        rrect(s, x, 2.28, 2.22, 2.45, fill, line=fill)
        text(s, x + 0.12, 2.55, 1.98, 0.4, name, 14.3, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, x + 0.12, 3.12, 1.98, 0.3, kind, 11.3, PALETTE["muted"], align="center", font_name=FONT)
        rect(s, x + 0.28, 3.58, 1.66, 0.02, PALETTE["white"])
        text(s, x + 0.14, 3.79, 1.94, 0.74, lesson, 11.5, PALETTE["ink"], align="center", font_name=FONT)
    text(s, 0.95, 5.14, 11.2, 0.56, "可借鉴：入口分层、状态清楚、教师工作区按任务分区。\n不可推断：本校已接入、具备同类资质/团队、具有市场规模或服务效果优势。", 13, PALETTE["ink"], font_name=FONT)
    text(s, 0.95, 6.0, 11.5, 0.42, "来源链接及证据类型见书面稿参考资料；访问日期按项目对标记录：2026-10-22。", 11.5, PALETTE["muted"], font_name=FONT)
    note(s, "参照的五个平台包括青海大学心理咨询预约流程、壹心理、简单心理、Togetherall和SimplePractice。前3个来源是公开门户或公开预约说明，后两个是官方帮助文档所描述的产品菜单。本轮没有登录其账户，也不把这些材料当作效果、价格、规模或资质比较。完整链接和访问边界见计划书参考资料。")

    # 9. Market model.
    s = slide_base(9, "08 市场容量", "先建立变量模型，再用校内证据估算", "当前缺少已验证采购规模、单校报价与外校意向，因此不报金额。")
    rrect(s, 1.0, 2.13, 11.1, 1.32, PALETTE["brand_soft"], line=PALETTE["brand_soft"])
    text(s, 1.38, 2.46, 10.35, 0.55, "年度可服务采购容量 = 符合条件院校数 N × 实际适用范围 × 年度单价 P", 21, PALETTE["brand"], True, align="center", font_name=FONT)
    labels = [(1.05, "N", "满足部署、隐私与服务条件的院校数", PALETTE["sage_soft"]),
              (4.82, "范围", "席位、功能和服务边界经校方确认", PALETTE["apricot_soft"]),
              (8.58, "P", "采购询价/采购规则核验后的年度单价", PALETTE["sage_soft"])]
    for x, title, body, fill in labels:
        rrect(s, x, 4.1, 3.35, 1.34, fill, line=fill)
        text(s, x + 0.18, 4.3, 2.98, 0.3, title, 16, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, x + 0.18, 4.74, 2.98, 0.48, body, 11.7, PALETTE["ink"], align="center", font_name=FONT)
    text(s, 1.12, 5.86, 10.8, 0.38, "先完成需求确认、成本询价、采购政策与安全评审；再决定N、范围和P。", 13.2, PALETTE["muted"], align="center", font_name=FONT)
    note(s, "市场容量用变量表达：符合安全、部署和服务条件的院校数乘以实际采购范围和经采购验证的年度单价。现在三个变量都未知，所以不估市场金额或收入。也要与校内人工流程、校园信息平台、问卷预约工具、商业心理平台和通用AI比较其权限、服务和成本边界。")

    # 10. Pilot gates.
    s = slide_base(10, "09 验证与试点", "试点之前先过责任、隐私、评测和恢复门槛", "是否试点、对象、样本规模与周期由学校批准，本项目不自动招募。")
    gates = [(1.0, "业务定义", "责任人/服务时间\n数据字段与可见范围", PALETTE["brand"]),
             (3.85, "隔离验证", "合成案例与权限测试\n故障/超时保留", PALETTE["sage"]),
             (6.7, "恢复演练", "独立目录备份\n验证恢复与回滚", PALETTE["apricot"]),
             (9.55, "试点决策", "校方批准后决定\n真实对象与周期", PALETTE["brand"])]
    for i, (x, title, body, color) in enumerate(gates):
        oval(s, x + 0.62, 2.35, 0.55, 0.55, color, line=color)
        text(s, x + 0.62, 2.47, 0.55, 0.28, str(i + 1), 15, PALETTE["white"], True, align="center", font_name=FONT)
        text(s, x, 3.12, 1.8, 0.35, title, 16, PALETTE["ink"], True, align="center", font_name=FONT)
        text(s, x - 0.12, 3.65, 2.05, 0.85, body, 12.4, PALETTE["muted"], align="center", font_name=FONT)
        if i < 3:
            arrow(s, x + 2.22, 2.55, 0.4, 0.2, PALETTE["grid"], line=PALETTE["grid"])
    rrect(s, 1.08, 5.15, 10.9, 0.8, PALETTE["rose_soft"], line=PALETTE["rose_soft"])
    text(s, 1.34, 5.38, 10.38, 0.32, "停止条件：越权披露、记录无法恢复、人工服务无人承接、持续错误承诺或模型数据边界不清。", 13, PALETTE["ink"], True, font_name=FONT)
    note(s, "试点需要先有校内业务和隐私责任人、服务安排、权限复核、模型和场景评测，以及备份恢复验证。当前没有招募、访谈或真实试点证据；计划稿仅描述条件式流程。若出现越权、恢复失败、人工无人承接或持续错误承诺，应停止试点并由校方决定后续处理。")

    # 11. Go to market.
    s = slide_base(11, "10 推广策略", "从校内需求论证开始，逐级作出决策", "采购、订阅和校际合作都是假设，须经制度与成本核验。")
    stages = [("需求确认", "业务/隐私/安全\n预算负责人"), ("封闭演示", "仅合成数据\n隔离环境审查"), ("条件性试点", "学校批准后\n可选小范围"), ("扩展评审", "复核证据、成本\n重新授权")]
    for i, (title, body) in enumerate(stages):
        x = 1.0 + i * 2.85
        fill = [PALETTE["brand_soft"], PALETTE["sage_soft"], PALETTE["apricot_soft"], PALETTE["brand_soft"]][i]
        rrect(s, x, 2.65, 2.35, 1.8, fill, line=fill)
        text(s, x + 0.16, 2.97, 2.03, 0.4, title, 15.5, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, x + 0.17, 3.55, 2.01, 0.65, body, 12.2, PALETTE["ink"], align="center", font_name=FONT)
        if i < 3:
            arrow(s, x + 2.42, 3.4, 0.31, 0.2, PALETTE["apricot"], line=PALETTE["apricot"])
    text(s, 1.05, 5.15, 10.8, 0.72, "首期可讨论：校内业务需求论证、创新创业评审和合成数据封闭演示。\n未经批准不联系外校/学生、不宣称商业化或效果、不发布未验证指标。", 14, PALETTE["muted"], font_name=FONT)
    note(s, "初期渠道以校内业务论证、创新创业评审和封闭的合成数据演示为主。校内采购、校际合作、软件订阅或服务收费，需经过采购政策、信息安全和持续服务能力审查后再讨论，不作收入承诺。")

    # 12. Budget model.
    s = slide_base(12, "11 预算模型", "预算按实际用量与询价核算，当前没有金额", "每项保留数量、单价、日期、税费和持续成本；学校核准前暂不填报。")
    items = [
        ("算力/API", "调用量 × 核验单价 + 并发容量", PALETTE["brand_soft"]),
        ("部署与备份", "实例、存储、流量、备份周期 × 单价", PALETTE["sage_soft"]),
        ("专业评审", "评审场次 × 校内核准标准", PALETTE["apricot_soft"]),
        ("测试运维", "隔离测试工时 × 标准 + 恢复演练", PALETTE["brand_soft"]),
        ("资料准备", "材料制作/培训场次 × 实际单价", PALETTE["sage_soft"]),
    ]
    for i, (name, formula, fill) in enumerate(items):
        y = 2.0 + i * 0.73
        rrect(s, 1.05, y, 2.5, 0.55, fill, line=fill)
        text(s, 1.22, y + 0.12, 2.16, 0.3, name, 13.5, PALETTE["brand"], True, font_name=FONT)
        text(s, 3.92, y + 0.11, 7.6, 0.32, formula, 13.2, PALETTE["ink"], font_name=FONT)
    rrect(s, 1.05, 5.92, 10.6, 0.62, PALETTE["white"], line=PALETTE["grid"])
    text(s, 1.28, 6.08, 10.12, 0.32, "总预算 = 各科目经核准金额之和｜预算、资金来源与拨付方式【待填写】", 13.8, PALETTE["brand"], True, align="center", font_name=FONT)
    note(s, "附件预算按算力/API、部署备份、专业评审、测试运维、资料准备五类列出变量和公式。当前没有模型服务配置或价格、生产资源询价、人员标准或校内预算审批，所以不填写金额。任何已有资源由管理方确认后才可列为配套。")

    # 13. Evidence and risk.
    s = slide_base(13, "12 风险与证据", "证据要分层，工程通过不等于上线或效果通过", "建议按技术、专业、业务、生产四道门禁逐步审查。")
    rows = [
        ("技术", "权限/登录/加载等隔离记录", "支持工程原型事实", PALETTE["sage_soft"]),
        ("专业", "合成案例待审、真实模型未测", "不报准确率或模型胜出", PALETTE["apricot_soft"]),
        ("业务", "团队、责任、服务时段和试点未定", "不宣称校方已批准", PALETTE["brand_soft"]),
        ("生产", "Linux/TLS与校级运行条件未就绪", "不宣称整体上线", PALETTE["rose_soft"]),
    ]
    for i, (level, ev, claim, fill) in enumerate(rows):
        y = 2.05 + i * 0.86
        rrect(s, 1.0, y, 1.65, 0.62, fill, line=fill)
        text(s, 1.13, y + 0.15, 1.4, 0.3, level, 13.5, PALETTE["brand"], True, align="center", font_name=FONT)
        text(s, 3.0, y + 0.15, 4.0, 0.34, ev, 12.4, PALETTE["ink"], font_name=FONT)
        text(s, 7.45, y + 0.15, 4.4, 0.34, claim, 12.4, PALETTE["muted"], font_name=FONT)
    rect(s, 3.0, 1.92, 8.85, 0.02, PALETTE["grid"])
    note(s, "项目证据分成工程、专业、业务和生产四个层次。现有隔离测试支持部分工程事实，但AI评测场景待专业审查、真实模型没有比较、校内责任和试点没有批准、生产Linux/TLS未完成。Docker构建失败或部署材料不齐时，尤其不能宣称上线。")

    # 14. Decision request.
    s = slide_base(14, "13 评审讨论", "先确认责任与条件，再决定是否进入试点", "这次希望明确校内下一步，而不是承诺尚未完成的服务和结果。")
    check = ["申报主体、项目来源与资格证明", "负责人、成员、指导教师与真实分工", "业务/隐私/运维/预算责任人", "模型提供商、数据边界与专业评审", "试点对象、周期、预算及停止条件", "本轮功能整合验收状态"]
    for i, item in enumerate(check):
        col = 0 if i < 3 else 1
        row = i if i < 3 else i - 3
        x = 1.0 + col * 5.7
        y = 2.05 + row * 1.0
        rrect(s, x, y, 5.1, 0.72, PALETTE["white"], line=PALETTE["grid"])
        oval(s, x + 0.2, y + 0.22, 0.25, 0.25, PALETTE["apricot"], line=PALETTE["apricot"])
        text(s, x + 0.62, y + 0.19, 4.25, 0.36, item, 13.1, PALETTE["ink"], font_name=FONT)
    rrect(s, 1.0, 5.52, 10.8, 0.72, PALETTE["brand_soft"], line=PALETTE["brand_soft"])
    text(s, 1.26, 5.7, 10.25, 0.34, "下一步建议：校内确认边界与责任人 → 完成隔离评测和恢复复核 → 由学校决定是否开展小范围验证", 13.3, PALETTE["brand"], True, align="center", font_name=FONT)
    note(s, "需要校内讨论的事项包括申报主体与资格、团队和指导教师、业务隐私运维预算责任人、模型及数据边界、专业评审、试点对象与周期，以及本轮功能的最终整合状态。下一步先确定责任，再完成隔离验证和独立复核，由学校决定是否开展试点。谢谢。")

    PPTX_OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(PPTX_OUT))
    reopened = InspectPresentation(str(PPTX_OUT))
    if len(reopened.slides) != 14:
        raise RuntimeError(f"Expected 14 slides, got {len(reopened.slides)}")
    for idx, slide in enumerate(reopened.slides, 1):
        if not slide.notes_slide.notes_text_frame.text.strip():
            raise RuntimeError(f"Slide {idx} is missing speaker notes")
    print(f"PPTX={PPTX_OUT}; slides={len(reopened.slides)}; editable native text/shapes; notes=14")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["docx", "pptx", "all"], default="all")
    args = parser.parse_args()
    if args.stage in ("docx", "all"):
        build_docx()
    if args.stage in ("pptx", "all"):
        build_pptx()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
