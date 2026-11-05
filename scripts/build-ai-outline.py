"""Build the compact editable eight-page defence outline, never a slide deck."""
import argparse
import hashlib
import json
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / 'tmp/ai-outline-20261027'
VERSION, UPDATED = '4.0', '2026-10-27'
INTRO = '建议演示共8页，包含封面和成果收束，按约5至7分钟准备。按最新申报书摘要与六章重排，每页3条要点，保留一项主要视觉及前后衔接讲稿。来源、数据口径和工程明细集中备查，不另增常规讲述页。'




PAGES = [{'title': '心域智链项目概览',
  'bullets': ['服务高校学生测评后的记录理解与人工支持。', '以现有平台为基础，拟完善统计、检索和摘要协作。', '首期拟面向湖北高校开展流程调研与产品验证。'],
  'visual': 'V01封面底板配V02相伴品牌，只保留项目名称和一句定位。',
  'before': '心域智链关注学生测评之后，记录怎样帮助教师提供后续支持。',
  'after': '先看申报书中与学生支持有关的背景和实际任务。',
  'state': '项目定位与计划；不是已有湖北试点或校方采用声明。',
  'refs': '申报书摘要、2.1、2.5、4.1。',
  'assets': ['V01', 'V02']},
 {'title': '项目背景与建设需求',
  'bullets': ['学业、就业、人际与生活适应压力需要持续关注。', '2024年本科生调查中，80.0%知晓校内免费咨询，2.8%曾使用。', '测评后还需要记录说明、清晰的求助入口和人工回应。'],
  'visual': 'V13咨询知晓与使用图作为唯一数据图，图外标调查对象和年份。',
  'before': '申报书把学生的成长压力与校内支持入口放在一起讨论。',
  'after': '项目围绕这些任务组织学生端和教师端功能。',
  'state': '60,782份有效本科生问卷；两项独立问项，不作漏斗或转化率。',
  'refs': '申报书1.1、1.3、1.4；表1、图3；参考文献[3]。',
  'assets': ['V13']},
 {'title': '产品与师生服务流程',
  'bullets': ['学生可完成测评、查看本人记录并发起求助或预约。', '教师在明确分配范围内查阅材料、人工答复并记录跟进。', '拟在两端之间补充有来源、可修改的AI摘要草稿。'],
  'visual': 'V04框内最多两张登记合成截图，展示学生求助与教师处理同一事项。',
  'before': '学生能够提出问题，教师能够查阅必要资料，是现有原型的基础。',
  'after': '新增AI能力应嵌入这条人工服务流程，下面说明其技术分工。',
  'state': '现有作答、查看与求助跟进原型；摘要和审核衔接仍为拟建设。',
  'refs': '申报书2.1至2.4；第五章表14。',
  'assets': ['V04']},
 {'title': '拟建设的AI分析链路',
  'bullets': ['拟由规则与统计代码统一检查字段，计算同口径记录的变化。', '模型拟依据已确认事实与审核资料起草摘要。', '草稿经校验和教师复核使用，生成失败时保留人工流程。'],
  'visual': 'V09受控流程图，只主讲统计事实、资料检索、摘要与人工复核。',
  'before': '统计负责可复算的事实，模型负责把事实和资料组织成草稿。',
  'after': '有了明确的产品与技术范围，再看首期应从哪些学校任务进入。',
  'state': '目标链路；当前局部统计已有，统一质量治理与受控摘要拟完善。',
  'refs': '申报书1.4、5.1至5.3；表13、14和图13。',
  'assets': ['V09']},
 {'title': '湖北高校市场与切入方式',
  'bullets': ['2024年湖北普通、职业高校133所，本专科在校生191.52万人。', '拟先从湖北高校测评后的求助、教师答复与记录整理切入。', '采购范围按软件、部署、维护和专业服务分别明确。'],
  'visual': '用133所和191.52万人两个数字配高校切入说明，完整地区表仅备查。',
  'before': '申报书比较了31地区教育规模，把湖北高校作为前期调研方向。',
  'after': '进入学校首先要理解流程，再通过演示与任务观察验证可用性。',
  'state': '2024年教育规模背景，不等于客户、心理服务需求或收入；中学独立拓展。',
  'refs': '申报书3.1至3.4；表7、9至11及地区数据。',
  'assets': ['V03']},
 {'title': '推广实施与任务验证',
  'bullets': ['先了解校内流程，形成角色、任务和待确认事项清单。', '用合成案例演示并修订原型，配套操作培训与维护说明。', '获批后观察任务完成、耗时、错误和教师草稿修改情况。'],
  'visual': '按流程了解、合成演示、培训维护、任务验证四步排版，不编周数。',
  'before': '推广从校内真实任务开始，演示用于发现需要修改的步骤。',
  'after': '这些工作需要明确责任分工，也需要据实核算资源。',
  'state': '拟开展的实施计划；参与人员、真实数据使用和时间由学校确认。',
  'refs': '申报书4.1至4.4；表12和第六章表16。',
  'assets': ['V03']},
 {'title': '组织分工与预算安排',
  'bullets': ['按研发、数据治理、专业审阅、校内业务与运维落实分工。', '预算按申报书六项科目，以实际用量和核实单价测算。', '人员、导师、周期、单价和金额留待负责人核实填写。'],
  'visual': '用责任角色与六条预算科目说明资源，金额均留待填写，不做预算饼图。',
  'before': '研发团队提供工程材料，校内及专业责任需要由相应人员确认。',
  'after': '最后把这些投入对应到具体交付和下一步工作。',
  'state': '组织与测算框架，未虚构已到位人员、预算或资源。',
  'refs': '申报书6.1、6.2；表15。',
  'assets': ['V03']},
 {'title': '预期成果与下一步',
  'bullets': ['形成可复验原型、数据图表、摘要与评测记录。', '交付操作培训、数据治理、部署维护与恢复材料。', '下一步确认责任与任务范围，完成隔离复验后申请小范围验证。'],
  'visual': 'V02品牌收束，列成果与近期任务；不再追加目录、章节或感谢页。',
  'before': '申报书的预期成果既包括软件，也包括评测、培训和运行材料。',
  'after': '请老师就高校任务范围、AI辅助分工和验证安排提出意见。',
  'state': '预期成果和后续计划，不表示整体上线、试点获批或效果验证完成。',
  'refs': '申报书6.3、6.4；表16及附录B。',
  'assets': ['V02']}]

SOURCES = [('R0', '申报材料S5图表增强审阅稿', '本轮内容依据；只读核对，不改动申报书。', '../../deliverables/心域智链项目申报材料_图表增强审阅稿.docx'),
 ('R1', '申报书同步源稿', '摘要与六章逐页映射，主讲只选必要内容。', '../../docs/plan/心域智链申报计划书.md'),
 ('R2',
  '2024年大学生心理健康状况调查报告 作者公开摘要',
  '80.0%与2.8%按申报书参考文献[3]及登记图复用。',
  'https://psy.china.com.cn/2025-06/20/content_43141390.htm'),
 ('R3',
  '教育部2024年分地区教育数据登记',
  '湖北高校133所和本专科191.52万人按申报书3.2复用。',
  '../../docs/plan/ai-application/revision-20261027/regional-education-2024.json'),
 ('R4',
  '科研图登记',
  '引用原有figures-sci图，不另做数据图。',
  '../../docs/plan/ai-application/sci-revision-20261027/figure-spec.json'),
 ('R5', '工程验收记录', '记录现有测试及整合阻塞，本轮不重跑业务测试。', '../../docs/test/文章分页与预览验收.md'),
 ('R6', 'S5申报书独立复核记录', '以当前v1.4最终结论为准，材料复核不等于试点或生产批准。', '../../docs/test/申报书数学分析与科研图复核.md')]
VISUALS = [('V01', '封面底板', 'docs/design/ppt-kit/cover-bg.svg'),
 ('V02', '相伴品牌', 'src/assets/brand/brand-logo-horizontal.svg'),
 ('V03', '同源图标', 'docs/design/ppt-kit/icon-sheet.svg'),
 ('V04', '合成截图框', 'docs/design/ppt-kit/screenshot-frames/screenshot-frame-16x9.svg'),
 ('V09', 'AI调用流程', 'docs/plan/ai-application/figures-sci/fig07-ai-workflow.svg'),
 ('V13', '咨询知晓与使用', 'docs/plan/ai-application/figures-sci/fig09-service.svg')]
NOTES = [('备查一 调查与湖北数据',
  '80.0%与2.8%来自2024年60,782份本科生有效问卷的不同问题，不能计算转化率或据此推断服务质量。2024年湖北133所为普通、职业高校，本专科191.52万人按同年地区口径，不与2025年全国数据混用，不直接换算客户、心理需求或收入。31地文献亚组、区间与教育集中度留申报书供追问，不另开演示页。'),
 ('备查二 现有工程与AI边界',
  '已有测评、局部统计、报告和可信分配范围内的求助跟进原型；统一质量治理、必要字段筛选、草稿来源、输出校验及审核衔接为拟建流程。RAG默认关闭，网关本地回退不证明外部模型接通；真实模型尚未评测。接入前需审查和限制外发原文路径，AI不作诊断、量表临床解释、危机裁定或自动处置。'),
 ('备查三 验证证据',
  '既有前端22单测、38合成页面场景、30文章交互通过。最新完整后端135通过、3条件跳过、5项WinError10013环境错误；真实UI因Vite代理connect '
  'EACCES阻塞，完整集成未通过。12条AI合成案例待专业审阅，不代表真实模型效果。AI评测失败和超时纳入全部启动调用分母，另列可评分分母。S5内容、结构和交付哈希已取得v1.4独立复核，但不等于用户样式批准、对外申报或生产放行。'),
 ('备查四 预算与填写事项',
  '六项预算为算力与API，部署存储备份，工具授权与专业评审，数据质量与AI评测，测试运维，培训材料。人员、导师、校内业务/专业/安全/运维责任、周期、用量、单价、总额、资金来源及询价依据均待填写。本轮大纲0表；后续若加表，须水平和垂直居中的三线表。图题放图外，来源与处理说明放备查。')]


def labelled(doc, label, value):
    p = doc.add_paragraph()
    p.add_run(label + '  ').bold = True
    p.add_run(value)
    p.paragraph_format.keep_together = True


def add_link(p, label, target):
    rel = p.part.relate_to(target, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True)
    link = OxmlElement('w:hyperlink')
    link.set(qn('r:id'), rel)
    run, text = OxmlElement('w:r'), OxmlElement('w:t')
    text.text = label
    run.append(text)
    link.append(run)
    p._p.append(link)


def configure(doc):
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(1.8)
    section.left_margin = section.right_margin = Cm(2.1)
    section.footer_distance = Cm(0.85)
    for name in ('Normal', 'Title', 'Heading 1', 'Heading 2', 'List Bullet', 'Caption'):
        st = doc.styles[name]
        st.font.name, st.font.size, st.font.bold = 'Microsoft YaHei', Pt(11), False
        st.font.color.rgb = RGBColor(0, 0, 0)
        fonts = st.element.get_or_add_rPr().get_or_add_rFonts()
        for key in ('ascii', 'hAnsi', 'eastAsia'):
            fonts.set(qn('w:' + key), 'Microsoft YaHei')
        for key in ('asciiTheme', 'hAnsiTheme', 'eastAsiaTheme'):
            fonts.attrib.pop(qn('w:' + key), None)
        st.paragraph_format.line_spacing = 1.1
        st.paragraph_format.space_after = Pt(4)
        for node in list(st.element.xpath('.//w:pBdr')):
            node.getparent().remove(node)
    doc.styles['Title'].font.size, doc.styles['Title'].font.bold = Pt(20), True
    for name in ('Heading 1', 'Heading 2'):
        st = doc.styles[name]
        st.font.size, st.font.bold = Pt(13), True
        st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(10), Pt(5)
        st.paragraph_format.keep_with_next = True
    st = doc.styles['List Bullet'].paragraph_format
    st.left_indent, st.first_line_indent = Cm(0.5), Cm(-0.25)
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    doc.core_properties.title, doc.core_properties.subject = '心域智链项目答辩大纲', '8页精简答辩大纲'
    doc.core_properties.author = '心域智链项目组'


def build_word(output):
    doc = Document()
    configure(doc)
    doc.add_paragraph('心域智链项目答辩大纲', 'Title')
    doc.add_paragraph(INTRO)
    for n, p in enumerate(PAGES, 1):
        if n > 1 and (n - 1) % 3 == 0:
            doc.add_page_break()
        doc.add_paragraph(f'{n:02d} {p["title"]}', 'Heading 1')
        for item in p['bullets']:
            doc.add_paragraph(item, 'List Bullet').paragraph_format.keep_together = True
        for label, key in [('主要视觉', 'visual'), ('承上', 'before'), ('启下', 'after')]:
            labelled(doc, label, p[key])
    doc.add_page_break()
    doc.add_paragraph('讲者备查', 'Heading 1')
    doc.add_paragraph('以下是答辩备稿资料，不另计为演示页，无需逐项上屏。')
    for title, content in NOTES:
        doc.add_paragraph(title, 'Heading 2')
        doc.add_paragraph(content)
    doc.add_page_break()
    doc.add_paragraph('来源与页面属性', 'Heading 1')
    for sid, title, description, target in SOURCES:
        p = doc.add_paragraph()
        p.paragraph_format.keep_with_next = True
        p.add_run(sid + '  ').bold = True
        add_link(p, title, target[3:] if target.startswith('../../') else target)
        doc.add_paragraph(description)
    for n, p in enumerate(PAGES, 1):
        doc.add_paragraph(f'第{n:02d}页  {p["state"]} 核对：{p["refs"]}').paragraph_format.keep_together = True
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def build_markdown(path):
    lines = ['# 心域智链项目答辩大纲', '', f'> owner: AI-OUTLINE ｜ version: {VERSION} ｜ status: 8页精简大纲 待审阅 ｜ updated: {UPDATED}', '', INTRO, '',
             '主线：项目与需求 → 产品服务 → AI实现 → 湖北市场 → 实施验证 → 组织预算 → 成果。', '',
             '[可编辑Word](../../deliverables/心域智链项目答辩大纲.docx) · [视觉清单](AI答辩大纲视觉清单.md)', '']
    for n, p in enumerate(PAGES, 1):
        lines += [f'## {n:02d} {p["title"]}', ''] + ['- ' + b for b in p['bullets']]
        lines += ['', '主要视觉：' + p['visual'], '', '承上：' + p['before'], '', '启下：' + p['after'], '']
    lines += ['## 讲者备查', '', '以下材料不上常规讲述页，不据此增加PPT页数。', '']
    for title, content in NOTES:
        lines += ['### ' + title, '', content, '']
    lines += ['## 来源与页面属性', '']
    for sid, title, description, target in SOURCES:
        lines += [f'{sid} [{title}]({target})。{description}', '']
    for n, p in enumerate(PAGES, 1):
        lines += [f'第{n:02d}页：{p["state"]} 核对：{p["refs"]}', '']
    lines += ['## 精简取舍', '', '上一版12页再压缩为8页，按S5申报书摘要与六章重排。删除单独的总体流程、方案价值及当前进展页；师生功能合为产品服务，统计和模型合为AI实现，实施与任务验证合并。湖北市场、组织预算与预期成果按申报书补齐，不仅删页码。来源和测试明细集中备查，不另增目录、章节或感谢页。', '',
              '只读复用最新科研图登记，不重绘或改动申报书，不修改三套模板预览。共享索引与团队记录由主对话Lead整合。', '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def build_visual_list(path):
    lines = ['# AI答辩大纲视觉清单', '', f'> owner: AI-OUTLINE ｜ version: {VERSION} ｜ status: 8页申报书对应大纲 ｜ updated: {UPDATED}', '',
             '本轮按最新申报书S5改为8个演示页，封面及成果收束均计入，不制作完整PPT。三套模板预览保留待选。', '',
             '## 来源与版式', '',
             '字体、品牌与颜色沿用[tokens](../../src/styles/tokens.css)、[素材登记](../../src/assets/manifest.json)、[PPT网格](../design/ppt-kit/16x9-grid.md)与[图表配色](../design/ppt-kit/chart-palette.json)。只用已登记approved素材，不引入装饰emoji或第二套视觉源。', '',
             '图表只读引用[科研图登记](../plan/ai-application/sci-revision-20261027/figure-spec.json)，图题放图外，来源及范围说明集中备查。数据页保留指标、单位、对象和年份。', '',
             '## 逐页采用方式', '']
    for n, p in enumerate(PAGES, 1):
        lines += [f'### 第{n:02d}页 {p["title"]}', '', p['visual'], '', '申报书映射：' + p['refs'], '']
    lines += ['## 登记素材', '']
    for sid, title, location in VISUALS:
        lines += [f'### {sid} {title}', '', f'[{location}](../../{location})', '']
    lines += ['## 取舍与数字边界', '',
              '第02页只用咨询知晓/使用图，不把两项独立问题画成漏斗。第03页最多两张登记合成截图。第04页合并原先分开的数据分析和模型连接，明确为拟建流程。第05页只讲湖北133所、191.52万人及切入任务，不堆全国、31地、采购金额或集中度图。', '',
              '四区域总体方案图及完整架构留在申报书备查，不再单占主讲页；第06页合并实施与验证，第07页对应申报书责任分工及六项预算，第08页对应预期成果和后续任务。当前0表，真实字段后填。', '',
              '## 本轮核验', '',
              '本轮依据S5正文和六章映射制作8页/24要点大纲，来源哈希与构建、原生Word只读渲染记录存放tmp/ai-outline-20261027/compact-v4/。实际目视与独立复核完成后追加结果。', '']
    path.write_text('\n'.join(lines), encoding='utf-8')


def validate_inputs():
    assert len(PAGES) == 8 and all(len(p['bullets']) == 3 for p in PAGES)
    ids = {v[0] for v in VISUALS}
    assert all(set(p['assets']) <= ids for p in PAGES)
    manifest = json.loads((ROOT / 'src/assets/manifest.json').read_text(encoding='utf-8'))
    for name in ['brand-logo-horizontal-svg', 'icon-domain-sprite-24-svg']:
        assert next(a for a in manifest['assets'] if a['id'] == name)['status'] == 'approved'
    registry = json.loads((ROOT / 'docs/plan/ai-application/sci-revision-20261027/figure-spec.json').read_text(encoding='utf-8'))
    figure_ids = {f['id'] for f in registry['figures']}
    for _, _, location in VISUALS:
        assert (ROOT / location).is_file(), location
        if 'figures-sci/' in location:
            assert Path(location).stem in figure_ids, location


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'deliverables/心域智链项目答辩大纲.docx')
    parser.add_argument('--report', type=Path, default=SCRATCH / 'compact-v4/build.json')
    parser.add_argument('--replace', action='store_true')
    args = parser.parse_args()
    output, report = args.output.resolve(), args.report.resolve()
    approved = (ROOT / 'deliverables/心域智链项目答辩大纲.docx').resolve()
    if output != approved and SCRATCH.resolve() not in output.parents:
        raise ValueError('Output must remain in the owned outline or task scratch path')
    if output.exists() and not args.replace:
        raise FileExistsError('Preserve the previous outline before using --replace')
    if SCRATCH.resolve() not in report.parents:
        raise ValueError('Report must remain in task scratch')
    validate_inputs()
    build_word(output)
    build_markdown(ROOT / 'docs/ppt/答辩方案.md')
    build_visual_list(ROOT / 'docs/ppt/AI答辩大纲视觉清单.md')
    application_sources = [ROOT / 'deliverables/心域智链项目申报材料_图表增强审阅稿.docx', ROOT / 'docs/plan/心域智链申报计划书.md']
    source_hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in application_sources}
    result = dict(version=VERSION, updated=UPDATED, output=str(output), recommended_pages=8, key_points=24, source_hashes=source_hashes,
                  tables=len(Document(output).tables), sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  pptx_created=False, runtime_or_database_changed=False, render_status='pending', independent_review='not claimed')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
