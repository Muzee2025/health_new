"""Complete the project plan while retaining the supplied forms and evidence."""
from pathlib import Path  # noqa: I001
from copy import deepcopy
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED
from urllib.parse import urlparse
import json
import re
from lxml import etree
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/project-plan-revision-20261029'
WORK.mkdir(parents=True, exist_ok=True)
BASE = ROOT / 'deliverables/心域智链项目计划书_系统内容与截图补充_20261029.docx'
OUT = ROOT / 'deliverables/心域智链项目策划书_内容完善修订稿_20261029.docx'
doc = Document(BASE)
old_paragraphs = list(doc.paragraphs)
paragraph_changes = []

def locate(prefix):
    return next(p for p in doc.paragraphs if p.text.startswith(prefix))

body_reference = locate('产品开发方面，')
h2_reference = locate('5.4 项目进展')
caption_reference = locate('图21 ')

def font(run, size=12, bold=False):
    run.font.name = 'Times New Roman'
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')

def change(p, text, size=12, bold=False):
    paragraph_changes.append({'before': p.text, 'after': text})
    p.clear()
    font(p.add_run(text), size, bold)

def insert(anchor, text, kind='body', page_break=False, keep_next=False):
    p = anchor.insert_paragraph_before()
    ref = h2_reference if kind == 'heading' else caption_reference if kind == 'caption' else body_reference
    if ref._p.pPr is not None:
        p._p.insert(0, deepcopy(ref._p.pPr))
    if kind != 'heading':
        p.style = doc.styles['Normal']
    p.paragraph_format.page_break_before = page_break
    p.paragraph_format.keep_with_next = keep_next or kind in ('heading', 'caption')
    p.paragraph_format.keep_together = True
    if kind in ('heading', 'caption'):
        p.paragraph_format.first_line_indent = Cm(0)
    if kind == 'caption':
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    font(p.add_run(text), 13 if kind == 'heading' else 10 if kind == 'caption' else 12, kind == 'heading')
    return p

# Clarify the planned school role in the existing task matrix.
school_table = doc.tables[6]
school_before = [c.text for c in school_table.rows[-1].cells]
school_after = ['学校（规划）', '在明确授权和管理范围内查看汇总情况', '拟提供按口径汇总的统计信息；数据使用和展示范围需经校方确认']
for cell, text in zip(school_table.rows[-1].cells, school_after):  # noqa: B905
    cell.text = text
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    for run in p.runs:
        font(run)
change(locate('表11 四项学校心理服务采购案例'), '表11 四项学校心理服务采购案例 [5]—[8]', size=10)

# Make progress concrete using the already verified local data deliverables.
change(locate('数据准备方面，'), '数据准备方面，已形成数据库变量工作簿、文献数据工作簿和公开资料包。字段字典以独立预览库的27表198字段为参考，并登记不同历史库的结构差异；文献整理覆盖6篇论文及26份去重下载文件，保留出处、单位、原文数值和处理说明。这些资料支持项目论证和后续复算，研究数据与业务数据库分开保存。')

# Chapter six must describe actual outputs and how they will be checked.
team_body = next(p for p in doc.paragraphs if p.text == '项目由研发、数据治理、专业审阅、校内业务和运行维护等角色协作完成。')
change(team_body, '项目按研发、数据整理、专业审阅、校内业务和运行维护划分职责。研发人员完善原型、权限与接口，保留测试和问题修复记录；数据整理人员维护字段口径、资料来源和处理版本；相关专业人员确认测评工具的适用范围、结果说明及案例；校内业务与运维责任方分别确认人工承接、访问权限、部署和恢复安排。具体承接人员、导师和实施周期由负责人核实后填写。')
budget_tail = locate('服务器、场地或人员投入如作为配套资源')
insert(budget_tail, '本表金额沿用附件暂列测算，合计5000元。实际执行前补齐数量、单价、报价日期和用途说明，由负责人按申报及财务要求复核；表中金额不表示采购完成或经费已经到位。')

appendix = locate('附录 系统截图与实现范围说明')
insert(appendix, '6.3 预期成果与检查方法', 'heading', page_break=True)
insert(appendix, '项目以可交付的软件、数据文件和工作记录说明成果。现有模块继续完善，AI摘要和校内任务验证按前置条件推进。表16将交付内容与检查方式对应，便于在项目结束时逐项核对。')
insert(appendix, '表16 预期成果与检查方法', 'caption')
rows = [
    ['成果', '交付内容', '检查方法'],
    ['软件原型\n已有基础', '学生与教师端功能、明确分配权限、留言答复和跟进流程', '在独立环境完成主要任务，记录通过、失败、跳过及原因；核对越权访问和异常提示'],
    ['数据与图表\n已有整理成果', '字段字典、来源清单、处理数据、图表及复算脚本', '按原始来源复算数值，核对单位、样本范围、重复与缺失；记录版本和排除原因'],
    ['AI辅助摘要\n拟完善并评测', '固定案例、摘要字段、引用依据、失败记录与教师修改意见', '对照案例核查事实、遗漏和引用；成功、超时与失败分别计数，说明评分分母'],
    ['操作与运行材料\n持续完善', '操作说明、权限说明、备份恢复与问题处理材料', '依据材料复走操作和恢复过程，记录环境、步骤、责任及待修事项'],
    ['任务验证记录\n获批后开展', '师生任务记录、使用反馈、人工承接和问题复盘', '预先约定任务、参与范围与记录方法，观察完成情况和耗时，再决定后续修改'],
]
table = doc.add_table(rows=len(rows), cols=3)
table.alignment = WD_TABLE_ALIGNMENT.CENTER
table.autofit = False
widths = [Cm(3.5), Cm(4.9), Cm(6.0)]
for column, width in zip(table.columns, widths):  # noqa: B905
    column.width = width
for row_index, (row, values) in enumerate(zip(table.rows, rows)):  # noqa: B905
    props = row._tr.get_or_add_trPr()
    props.append(OxmlElement('w:cantSplit'))
    if row_index == 0:
        props.append(OxmlElement('w:tblHeader'))
    for cell, value, width in zip(row.cells, values, widths):  # noqa: B905
        cell.width = width
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        cell.text = value
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        for run in p.runs:
            font(run, 11.5, row_index == 0)
        if row_index == 0:
            borders = OxmlElement('w:tcBorders')
            edge = OxmlElement('w:bottom')
            edge.set(qn('w:val'), 'single'); edge.set(qn('w:sz'), '6')  # noqa: E702
            borders.append(edge); cell._tc.get_or_add_tcPr().append(borders)  # noqa: E702
tbl_pr = table._tbl.tblPr
borders = OxmlElement('w:tblBorders')
for name in ('top', 'bottom', 'left', 'right', 'insideH', 'insideV'):
    edge = OxmlElement('w:' + name)
    edge.set(qn('w:val'), 'single' if name in ('top', 'bottom') else 'nil')
    if name in ('top', 'bottom'):
        edge.set(qn('w:sz'), '12')
    borders.append(edge)
tbl_pr.append(borders)
appendix._p.addprevious(table._tbl)
insert(appendix, '6.4 阶段安排与交付', 'heading')
for text in [
    '第一阶段完善原型。用合成案例复走测评、留言、答复、跟进和导出，核对权限与异常提示，保存测试结果、失败说明和问题清单。',
    '第二阶段完善资料与摘要。在获准范围内明确资料、字段和模型版本，以固定案例核查事实、引用、失败及人工修改，形成评测记录。',
    '第三阶段开展校内任务验证。学校确认参与范围、承接与退出方式后，观察任务完成情况和耗时，收集师生反馈并修正流程。',
    '第四阶段准备运行交接。核对目标环境的权限、备份恢复和维护责任，形成操作与交接材料；具体日期待负责人确认，未决问题继续登记。',
]:
    insert(appendix, text)

change(appendix, '附录A 系统截图与实现范围说明', size=13, bold=True)

# Restore the missing source list from the existing registered manuscript.
support_table = next(t for t in doc.tables if t.cell(0, 0).text.startswith('附录1'))
support_anchor_element = support_table._tbl.getprevious()
from docx.text.paragraph import Paragraph  # noqa: E402, I001
support_anchor = Paragraph(support_anchor_element, doc._body)
insert(support_anchor, '附录B 资料口径与参考来源', 'heading', page_break=True)
for text in [
    '筛查与调查：正文的风险分组、筛查阳性比例和学业感知按原研究对象及题项解释。不同调查不合并成同一总体；80.0%的知晓比例与2.8%的曾使用比例来自独立问项，不据此计算转化率。横断调查及不同研究亚组也不作为同一批学生的纵向变化。',
    '教育与采购资料：全国教育规模和31省份教育统计保留各自年份及学段口径，用于理解服务场景，不等于客户或心理问题人数。四项采购案例的服务范围不同，成交金额只作范围参照，不直接作为本项目定价或收入依据。',
    '项目阶段资料：数据库字段清单以2026年10月28日整理结果为依据，独立预览库与历史库分别登记，不能由字段清单推定当前运行服务绑定。公开论文资料单独保存，不混入业务数据库，也不把论文中的关联解释为项目已验证的因果效果。',
    '以下来源编号沿用正文及项目既有资料登记，用于补齐附件中的引注出处。图14至图21的界面来源和合成数据说明见附录A。',
]:
    insert(support_anchor, text)
source_text = (ROOT / 'docs/plan/心域智链申报计划书.md').read_text(encoding='utf-8')
references = []
for number, body in re.findall(r'^\[(\d+)\]\s+(.+)$', source_text, re.M):
    number = int(number)
    if number > 26:
        continue
    match = re.search(r'https?://\S+', body)
    assert match
    url = match.group(0)
    title = body[:match.start()].strip()
    p = insert(support_anchor, f'[{number}] {title} ')
    p.paragraph_format.left_indent = Cm(.72)
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.first_line_indent = Cm(-.72)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.15
    for run in p.runs:
        font(run, 10.5)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), doc.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement('w:r'); rp = OxmlElement('w:rPr')  # noqa: E702
    fonts = OxmlElement('w:rFonts'); fonts.set(qn('w:eastAsia'), '宋体'); fonts.set(qn('w:ascii'), 'Times New Roman'); rp.append(fonts)  # noqa: E702
    size = OxmlElement('w:sz'); size.set(qn('w:val'), '21'); rp.append(size)  # noqa: E702
    color = OxmlElement('w:color'); color.set(qn('w:val'), '1F4E79'); rp.append(color)  # noqa: E702
    underline = OxmlElement('w:u'); underline.set(qn('w:val'), 'single'); rp.append(underline)  # noqa: E702
    run.append(rp); text = OxmlElement('w:t'); text.text = f'原文链接（{urlparse(url).hostname}）'; run.append(text)  # noqa: E702
    hyperlink.append(run); p._p.append(hyperlink)  # noqa: E702
    references.append({'number': number, 'title': title, 'url': url})
assert [x['number'] for x in references] == list(range(1, 27))

candidate = WORK / 'candidate-package.docx'
doc.save(candidate)
allowed = {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
with ZipFile(BASE) as base, ZipFile(candidate) as generated, ZipFile(OUT, 'w', ZIP_DEFLATED) as output:
    assert set(base.namelist()) == set(generated.namelist())
    for name in base.namelist():
        output.writestr(name, generated.read(name) if name in allowed else base.read(name))

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
canonical = lambda node: etree.tostring(node, method='c14n', exclusive=True)  # noqa: E731
with ZipFile(BASE) as base, ZipFile(OUT) as output:
    base_xml, out_xml = [etree.fromstring(z.read('word/document.xml')) for z in (base, output)]
    old_tables = base_xml.findall('.//w:tbl', ns)
    new_tables = out_xml.findall('.//w:tbl', ns)
    assert len(old_tables) == 19 and len(new_tables) == 20
    # Original body table 6 has an intentional school-role wording correction.
    for i, old in enumerate(old_tables):
        j = i if i < 17 else i + 1
        if i != 6:
            assert canonical(old) == canonical(new_tables[j]), i
    for tag in ('w:sectPr', 'm:oMath'):
        assert [canonical(e) for e in base_xml.findall('.//' + tag, ns)] == [canonical(e) for e in out_xml.findall('.//' + tag, ns)]
    retained = [n for n in base.namelist() if n not in allowed]
    assert all(base.read(n) == output.read(n) for n in retained)
    media = [n for n in base.namelist() if n.startswith('word/media/')]
    assert len(media) == 25 and all(base.read(n) == output.read(n) for n in media)

report = {'owner': 'A', 'updated': '2026-10-29', 'base': str(BASE), 'baseSha256': sha256(BASE.read_bytes()).hexdigest(), 'output': str(OUT), 'sha256': sha256(OUT.read_bytes()).hexdigest(), 'tables': 20, 'originalTablesUnchanged': 18, 'originalTableChanged': {'index': 6, 'before': school_before, 'after': school_after}, 'newTableCaption': '表16 预期成果与检查方法', 'mediaPreserved': 25, 'sectionsPreserved': 3, 'formulaNodesPreserved': 4, 'nonBodyPartsBytePreserved': len(retained), 'paragraphChanges': paragraph_changes, 'referencesRestored': references, 'referenceSource': 'docs/plan/心域智链申报计划书.md', 'referenceSourceSha256': sha256(source_text.encode('utf-8')).hexdigest(), 'referenceRebrowsePerformed': False}
(WORK / 'build-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: report[k] for k in ('output', 'sha256', 'tables', 'mediaPreserved', 'sectionsPreserved', 'formulaNodesPreserved', 'nonBodyPartsBytePreserved')}, ensure_ascii=False))
