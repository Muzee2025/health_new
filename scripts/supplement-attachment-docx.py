"""Supplement the supplied application, preserving all original non-body parts."""
from pathlib import Path  # noqa: I001
from copy import deepcopy
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED
import json
from lxml import etree
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/attachment-system-20261029'
SOURCE = WORK / 'source-private.docx'
OUTPUT = ROOT / 'deliverables/心域智链项目计划书_系统内容与截图补充_20261029.docx'
doc = Document(SOURCE)
original = list(doc.paragraphs)
body_reference = original[127]
h2_reference = original[126]
caption_reference = original[132]
changes = []

def replace(index, text):
    p = original[index]
    before = p.text
    p.clear()
    p.add_run(text)
    changes.append({'original_paragraph_index': index, 'before': before, 'after': text})

def insert(anchor, text='', kind='body', page_break=False, keep_next=False, bold=False):
    p = anchor.insert_paragraph_before()
    reference = h2_reference if kind == 'h2' else caption_reference if kind == 'caption' else body_reference
    if reference._p.pPr is not None:
        p._p.insert(0, deepcopy(reference._p.pPr))
    if kind != 'h2':
        p.style = doc.styles['Normal']
    fmt = p.paragraph_format
    fmt.page_break_before = page_break
    fmt.keep_with_next = keep_next or kind == 'h2'
    fmt.keep_together = True
    if kind in ('caption', 'image', 'label', 'h2'):
        fmt.first_line_indent = Cm(0)
    if kind in ('caption', 'image'):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if kind == 'image':
        fmt.space_before = Pt(5)
        fmt.space_after = Pt(3)
        fmt.line_spacing = 1
    run = p.add_run(text)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(13 if kind == 'h2' else 12)
    run._element.get_or_add_rPr().rFonts.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia', '宋体')
    if kind == 'h2':
        run.bold = True
    if kind == 'caption':
        run.font.size = Pt(10)
        fmt.space_after = Pt(8)
    if kind == 'label' or bold:
        run.bold = True
    return p

# Put a clear project introduction on the existing abstract page, retaining six chapters.
anchor = original[21]
insert(anchor, '项目介绍', 'h2')
for text in [
    '心域智链AI+校园心理支持协作平台以高校学生和心理教师为主要使用者，围绕“了解自己的记录—发起沟通—教师回应—持续跟进”组织服务。项目希望解决测评、对话和求助记录分散的问题，让学生找到下一步入口，也让教师在授权范围内连续查看和处理事项。',
    '目前已形成学生端和教师端的软件原型。学生端涵盖个人近况、心理测评、预约咨询、心理科普、智能助手、个人报告、匿名树洞及向老师留言；教师端涵盖工作台、求助与跟进、分配学生档案、预约安排、内容维护和干预记录。第五章展示当前系统界面及相应操作。',
    '项目采用Vue前端、FastAPI后端和SQLite数据存储。现阶段以已有业务流程和本地分析能力为基础，后续再完善资料检索、摘要起草与人工核对。预期交付包括可演示的软件、操作材料、数据整理成果与评测记录，并依据校内承接安排推进试点。',
]:
    insert(anchor, text)

replace(68, '现有功能：学生端已设置个人近况、心理测评、预约咨询、心理科普、智能助手、个人报告、匿名树洞和留言入口。测评页面包含量表选择、作答进度、答案修改和结果展示；科普列表支持搜索、分类、排序与分页；预约和留言分别保留处理状态，便于学生继续查阅。')
insert(original[69], '教师端已设置工作台、求助与跟进、学生管理、个体档案、预约管理、内容管理和干预记录。工作区将学生可见答复与内部跟进备注分开保存；个体档案提供测评、对话、预约和干预材料的查看入口，并设有Word导出操作。学生材料的读取、处理和导出均受明确的师生分配关系约束。')
replace(126, '5.1 系统架构与记录流转')
replace(127, '现有系统采用前后端分离结构。Vue前端按学生和教师角色组织页面，FastAPI后端处理登录鉴权、业务校验和记录读写，SQLite保存用户、测评、会话及消息、预约、文章、留言、师生关联、预警、跟进与审计等数据。浏览器通过业务接口请求资料，由后端核对当前用户身份和资源权限后返回。')
insert(original[128], '学生完成测评或提交留言后，可在自己的页面查看结果与状态；教师通过工作台和求助与跟进工作区处理分配范围内的事项，再分别形成学生可见答复、内部任务或干预记录。教师查看个体档案时，可以按时间回顾已有材料，并按权限导出个体Word报告。科普文章与教师资料另设维护入口，支持日常内容更新和预约安排。')
insert(original[128], '师生访问范围由独立的分配关系维护，不以学生自由填写的导师姓名自动授予权限。规则分析、报告展示与外部模型服务在实现中分别组织；模型适配接口已经预留，资料检索属于可选能力，实际模型接入和专业效果仍需另行评测。下一步的数据整理要求如下。')

screens = [
    ('student-dashboard', '（1）个人近况与服务入口', '图14 学生端个人近况界面',
     '学生进入首页后，可以直接选择测评、预约、向老师留言或与助手对话。近期洞察区域将情绪趋势、量表得分、树洞词频和预约情况分别展示，便于回顾自己的使用记录。',
     '系统将不同来源的记录分开呈现，帮助学生从查看信息转向具体操作。除了首页入口，侧边导航还可进入科普文章、树洞和个人报告等页面。'),
    ('student-test', '（2）心理测评与逐题作答', '图15 学生端心理测评作答界面',
     '心理测评先展示可选择的量表，进入作答后显示当前题号、已完成题数、选项与进度条。学生可以返回上一题修改答案；未完成时由页面提示继续作答，提交后进入结果展示。',
     '测评模块与个人记录相连，便于后续查看。量表的适用范围、版本和解释规则需要由专业人员确认，系统展示结果用于记录回顾与沟通参考。'),
    ('student-chat', '（3）智能助手与人工沟通入口', '图16 学生端智能助手界面',
     '智能助手页面设置会话列表、历史搜索、对话模式、消息区和输入区，支持查找与继续已有会话；“向老师留言”入口连接人工支持流程。页面同时保留会话分析区域，区分有记录和暂无分析数据的状态。',
     '本图展示会话组织与沟通入口。外部模型的实际可用性、回复质量和摘要核对流程需要在后续接入评测中分别确认，不能仅凭界面显示判断效果。'),
    ('student-report', '（4）个人报告与记录回顾', '图17 学生端个人报告界面',
     '个人报告集中展示当前分析结果、维度指标和相关图表，提供重新分析、打印报告及分享说明等操作入口。学生可先查看概况，再结合自己的原始记录理解某一时段的变化。',
     '报告模块是已有数据的呈现与分析入口。后续将进一步补齐时间范围、记录数量、来源说明和缺失状态，使每项结果更便于追溯与复核。'),
    ('teacher-dashboard', '（1）教师工作台与待处理事项', '图18 教师端工作台界面',
     '教师工作台汇集分配范围内的待审核预警、审核历史和统计趋势，并提供求助与跟进工作区入口。页面下方按已分配学生、对话消息、待处理预警等口径展示工作观察数据。',
     '教师从工作台进入具体学生或事项，结合已有资料进行人工核查。缺少楼宇等字段时，页面保留暂无可用数据的状态；群体统计不扩大到未分配学生。'),
    ('teacher-support', '（2）留言答复与内部跟进', '图19 教师端求助与跟进界面',
     '求助与跟进工作区分为学生提问、预警与审核记录、跟进任务三个区域。教师可在待答复列表填写给学生的回复，也可从留言或预警创建内部跟进任务，填写摘要和计划完成时间。',
     '跟进任务按进行中、已完成和已取消分类；完成任务时记录结果，取消时保留原因。学生可见答复与教师内部备注分开保存，便于区分沟通内容和工作记录。'),
    ('teacher-student', '（3）个体档案与材料导出', '图20 教师端学生档案界面',
     '个体档案将学生基本信息、测评时间轴、脱敏对话、预约、树洞标签汇总和干预记录放在同一页面，帮助教师回顾材料的先后关系。教师可添加干预记录，并从页面入口导出个体Word报告。',
     '档案查看和导出遵守同一分配权限。这里的导师显示字段只用于资料呈现；实际可访问范围由明确的师生关联与后端校验确定。'),
    ('teacher-content', '（4）内容维护与服务配套', '图21 教师端内容管理界面',
     '内容管理页分设文章管理和心理老师管理。文章列表支持按标题、摘要或来源搜索、按分类筛选、分页及阅读操作，并提供新增和删除入口；教师资料用于展示服务信息和预约安排。',
     '当前项目已整理平台阅读、留言、预约、测评、AI助手、跟进、隐私和账号安全等八篇使用指南。截图以这些已有指南展示列表结构，供后续培训和操作说明使用。'),
]
anchor = original[139]
insert(anchor, '5.4 项目进展', 'h2')
for text in [
    '产品开发方面，已形成学生端和教师端原型，完成测评、会话、报告、预约、文章、留言、档案及干预记录等模块的页面与接口实现。求助与跟进工作区进一步补充了留言答复、预警审核历史和内部跟进任务，显式师生关联用于约束教师访问范围。',
    '数据准备方面，已整理本地数据库变量清单，并完成公开论文数据的下载、清理与来源登记，形成可筛选的Excel工作簿和公开资料包。整理结果区分原文数值、处理后的指标及可能解释，作为项目论证和后续评测的资料基础；这些研究数据独立保存，未直接写入业务数据库。',
    '验证与材料方面，已保留本机模块测试和隔离演示记录，本次补充八个当前系统页面的截图及功能说明。当前交付仍属于软件原型与申报材料阶段，完整运行环境复验、专业人员审查、真实模型评测和校内试点尚待完成。下一阶段先复验业务连通与权限，再确认资料和模型范围，随后按获批安排开展试点。',
]:
    insert(anchor, text)
for i, (name, label, caption, description, extra) in enumerate(screens):
    if i in (0, 4):
        insert(anchor, '5.5 学生端功能实现' if i == 0 else '5.6 教师端功能实现', 'h2', page_break=True)
    insert(anchor, label, 'label', page_break=i not in (0, 4), keep_next=True)
    insert(anchor, description, keep_next=True)
    p = insert(anchor, kind='image', keep_next=True)
    p.add_run().add_picture(str(WORK / 'screens' / f'{name}.png'), width=Cm(14.45))
    insert(anchor, caption + '（合成演示）', 'caption')
    insert(anchor, extra)

insert(anchor, '5.7 当前系统与后续建设的衔接', 'h2')
for text in [
    '当前系统已将学生记录、求助入口、教师查看与处理串接为可继续开发的业务原型。预约管理承担时间与状态协调，科普与使用指南承担日常说明，树洞提供表达入口，干预记录保存后续处理材料。这些模块共同支撑“发现需要—主动求助—人工回应—记录跟进”的工作过程。',
    '后续建设重点是把已有记录整理成可核对的摘要材料，并完善资料来源管理、缺失与版本说明、模型失败处理和人工更正记录。教师端原始材料与摘要草稿的逐项对照仍属于下一步建设内容；真实模型接入、学校责任安排和试点效果也需要分别确认。',
]:
    insert(anchor, text)

# An appendix note follows chapter six, before the unchanged supporting materials.
appendix_anchor = original[146]
insert(appendix_anchor, '附录 系统截图与实现范围说明', 'h2', page_break=True)
for text in [
    '图14至图21于2026年10月29日由本项目当前前端源代码构建并渲染，截取相应页面的主内容区域。截图采用独立浏览器环境与预设合成接口数据，未读取实际学生记录或连接运行数据库，未调用真实模型。截图中的姓名、编号、对话、分值、日期和数量均为演示用途；科普列表引用项目已有的八篇平台使用指南。',
    '界面中的量表常模、风险等级、置信度及图表数值沿用当前原型字段，仅用于说明页面结构。它们不代表已校准的患病概率、统一风险界值或诊断结论，也不作为项目服务效果的证据。智能助手对话中的回复为预设示例，不能用来证明模型实际生成能力。',
    '本次补充核对了页面路由、前端功能入口、后端权限与支持流程代码。界面截图说明当前原型的呈现方式，不等同于整套系统的运行验收、专业批准或生产放行。原文图1至图13、表格、数学公式、参考信息和后附证明材料均予保留。',
]:
    insert(appendix_anchor, text)

# Keep supporting awards/transcript starting on their own page, as in the source.
from docx.oxml import OxmlElement  # noqa: E402, I001
support_break = OxmlElement('w:p')
support_props = OxmlElement('w:pPr')
support_props.append(OxmlElement('w:pageBreakBefore'))
support_spacing = OxmlElement('w:spacing')
support_spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}before', '0')
support_spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}after', '0')
support_spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}line', '20')
support_spacing.set('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}lineRule', 'exact')
support_props.append(support_spacing)
support_break.append(support_props)
doc.tables[17]._tbl.addprevious(support_break)

intermediate = WORK / 'candidate-package.docx'
doc.save(intermediate)
allowed = {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}
with ZipFile(SOURCE) as src, ZipFile(intermediate) as generated, ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as dst:
    originals = set(src.namelist())
    new_names = [name for name in generated.namelist() if name not in originals]
    assert all(name.startswith('word/media/') for name in new_names), new_names
    for name in src.namelist():
        dst.writestr(name, generated.read(name) if name in allowed else src.read(name))
    for name in new_names:
        dst.writestr(name, generated.read(name))

ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
with ZipFile(SOURCE) as src, ZipFile(OUTPUT) as dst:
    old_xml = etree.fromstring(src.read('word/document.xml'))
    new_xml = etree.fromstring(dst.read('word/document.xml'))
    canonical = lambda e: etree.tostring(e, method='c14n', exclusive=True)  # noqa: E731
    original_tables = old_xml.findall('.//w:tbl', ns)
    final_tables = new_xml.findall('.//w:tbl', ns)
    assert [canonical(e) for e in original_tables] == [canonical(e) for e in final_tables]
    assert [canonical(e) for e in old_xml.findall('.//w:sectPr', ns)] == [canonical(e) for e in new_xml.findall('.//w:sectPr', ns)]
    assert [canonical(e) for e in old_xml.findall('.//m:oMath', ns)] == [canonical(e) for e in new_xml.findall('.//m:oMath', ns)]
    preserved_parts = [name for name in src.namelist() if name not in allowed]
    assert all(src.read(name) == dst.read(name) for name in preserved_parts)
    report = {
        'source_sha256': sha256(SOURCE.read_bytes()).hexdigest(),
        'output': str(OUTPUT), 'output_sha256': sha256(OUTPUT.read_bytes()).hexdigest(),
        'tables_preserved': len(original_tables), 'sections_preserved': len(old_xml.findall('.//w:sectPr', ns)),
        'formula_nodes_preserved': len(old_xml.findall('.//m:oMath', ns)),
        'original_media_preserved': len([n for n in src.namelist() if n.startswith('word/media/')]),
        'non_body_parts_byte_preserved': len(preserved_parts), 'new_media': new_names,
        'modified_original_paragraphs': changes, 'new_screenshots': 8,
    }
(WORK / 'document-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: v for k,v in report.items() if k not in ('modified_original_paragraphs', 'new_media')}, ensure_ascii=False))
