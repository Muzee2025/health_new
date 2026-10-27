"""Assemble six Luna-authored chapters, centered native tables and source-backed figures."""
import sys,re,json,hashlib,argparse,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];QA=ROOT/'tmp/ai-application-20261027'
SKILL=Path('C:/Users/14012/.agents/skills/math-modeling')
sys.dont_write_bytecode=True
sys.path.insert(0,str(SKILL/'tools/docx/scripts'))
import paper_format as pf
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt,Cm,RGBColor

SOURCE=ROOT/'docs/plan/ai-application'
TEMPLATE=Path('C:/University/Files/附件.docx')
TEMPLATE_SHA256='2531a2432493e4592d0759473fb3add5b6e1770e3c69ef1ee501d31b1943202a'
REFERENCES=[
('郭菲等 2024年青少年心理健康与学业状况调查报告','https://psy.china.com.cn/2025-05/27/content_43126660.htm'),
('李春玲 高云浩 学业和就业竞争压力下大学生社会心态特征','https://sociology.cssn.cn/shxsw/swx_kycg/swx_xslw/202410/W020241025423030106787.pdf'),
('方圆等 2024年大学生心理健康状况调查报告 作者公开摘要','https://psy.china.com.cn/2025-06/20/content_43141390.htm'),
('教育部 2025年全国教育事业发展统计公报','https://www.moe.gov.cn/jyb_sjzl/sjzl_fztjgb/202607/t20260706_1442870.html'),
('四川邮电职业技术学院 心理健康测评系统成交公告 N5100012026001455','https://www.ccgp.gov.cn/cggg/dfgg/zbgg/202607/t20260715_26941179.htm'),
('中国劳动关系学院 智能心理测评与服务系统成交公告 ZYZB-2026-0788','https://www.ccgp.gov.cn/cggg/zygg/cjgg/202609/t20260909_27295534.htm'),
('龙泉驿区教育局 2026年中小学生心理健康状况测评服务成交公告','https://www.ccgp.gov.cn/cggg/dfgg/cjgg/202605/t20260514_26566118.htm'),
('成都市教科院 2026年中小学心理健康资源建设及关护行动成交公告 N5101012026000770','https://www.ccgp.gov.cn/cggg/dfgg/cjgg/202607/t20260701_26848948.htm'),
('教育部 全国学生心理健康工作咨询委员会第二次全体会议召开','https://www.moe.gov.cn/jyb_zzjg/huodong/202505/t20250529_1192362.html'),
('教育部等 全面加强和改进新时代学生心理健康工作专项行动计划2023至2025','https://www.moe.gov.cn/srcsite/A17/moe_943/moe_946/202305/t20230511_1059219.html'),
('教育部 全面推进健康学校建设指导意见','https://www.moe.gov.cn/srcsite/A17/moe_943/moe_946/202602/t20260227_1429365.html'),
]
URLREF={url:i for i,(_,url) in enumerate(REFERENCES,1)}
TITLES=['实用性与创新力','产品与服务','市场分析','营销策略与服务实施','方案实现','项目预算与预期成果']
ABSTRACT='本项目围绕青少年成长困扰及高校学生学业、就业与适应压力，建设以心理测评、授权持续监测和人工支持衔接为主线的AI+校园心理支持协作平台。申报书结合青少年与大学生调查、教育部统计和公开采购公告，以数据表及统计图呈现服务背景，重点说明测评结果之后的信息理解、变化观察与人工承接需要。技术方案将结构化业务记录、可复算统计分析和受控大模型辅助区分：数据分析用于质量检查与同口径趋势，大模型在审批后的最小上下文和审核知识范围内辅助摘要与材料组织，授权人员负责复核、答复和跟进。现有系统已经形成学生与教师工作区、角色及明确分配权限和部分分析接口；拟增强模块、真实模型评测和学校试点按阶段验收。首期聚焦高校，初中和高中作为需独立适配的拓展方向。申报成果包括可复验原型、分析模块、受控模型接入与评测材料、部署恢复和业务实施文档。测评与AI输出不替代诊断或现实处置；真实人员、周期、经费与学校批准信息由负责人后续核实填写。'
FORM_SUMMARY='本项目面向高校学生心理测评后的记录理解、授权教师复核与支持衔接，建设AI+校园心理支持协作平台。平台连接测评、趋势查看、求助答复、跟进和个体导出，以明确师生分配关系控制教师访问。拟增强的数据分析用于质量检查和可复算统计，大模型仅整理已确认事实与审核资料，形成待人工复核草稿。现有原型仍需稳定环境整合复验，专业工具适配、真实模型评测及校内试点待批准；初高中作为独立适配方向。人员、导师、周期和经费后期填写。'

def front_matter(doc):
    """Retain and fill the three supplied forms; never drop required application fields."""
    spec=importlib.util.spec_from_file_location('original_form',ROOT/'scripts/build-application-document.py')
    forms=importlib.util.module_from_spec(spec);spec.loader.exec_module(forms)
    body=doc.element.body;children=list(body);tables=body.findall(qn('w:tbl'))
    if len(tables)!=3:raise ValueError('Original attachment form contract changed')
    def cell(t,r,c):return tables[t].findall(qn('w:tr'))[r].findall(qn('w:tc'))[c]
    project='心域智链AI+校园心理支持协作平台'
    forms.fill_cell(cell(0,0,1),project)
    for row in list(range(3,8))+[9,10]:
        for c in tables[0].findall(qn('w:tr'))[row].findall(qn('w:tc'))[1:]:forms.fill_cell(c,'【待填写】')
    forms.fill_cell(cell(0,12,1),FORM_SUMMARY)
    for row,col,value in [(0,1,project),(1,1,'【待填写】元'),(2,1,'【待填写】'),(2,3,'【待填写】'),(4,0,FORM_SUMMARY)]:
        forms.fill_cell(cell(1,row,col),value)
    for row in range(7):forms.fill_cell(cell(2,row,2),project if row==0 else '【待填写】')
    for t in children[14].iter(qn('w:t')):
        if t.text:t.text=t.text.replace('（模板）','')
    for e in list(body)[19:]:
        if e.tag!=qn('w:sectPr'):body.remove(e)
    for i,t in enumerate(tables):forms.three_line_table(t,header_row=2 if i==0 else 0)
    for t in doc.tables:
        for row in t.rows:
            for cell_obj in row.cells:
                cell_obj.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                for p in cell_obj.paragraphs:
                    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.first_line_indent=Pt(0)
    # Source includes blank signature/opinion areas: retain them without invented entries.

def harmonize(text,ch):
    """Lead's tracked editorial decisions; frozen Luna source chapters stay unchanged."""
    text=text.replace('AI不作测评解释、诊断、风险裁定或自动处置。',
      'AI只把已确认的结构化事实与审核资料整理为通俗草稿，不解释量表的临床意义，不作诊断、风险裁定或自动处置。')
    text=text.replace('模型不用于测评解释、诊断、风险裁定或自动处置。',
      '模型仅整理已确认的事实与审核资料，不解释量表的临床意义，不作诊断、风险裁定或自动处置。')
    text=text.replace('AI依据结构化结果和审核资料起草说明，区分事实与解释，并提示缺失和规则限制。',
      'AI仅将已经确认的结构化事实和审核资料整理为通俗草稿，标明数据缺失与规则限制，不解释分数的临床意义。')
    text=text.replace('图表说明或通俗解释','图表说明或通俗呈现已确认事实').replace('带依据的摘要草稿、解释性文字','带依据的摘要草稿、事实说明文字')
    text=text.replace('把统计质量检查、经审核知识检索、结构化生成、来源展示及人工复核整合',
                      '将统计质量检查、经审核知识检索、结构化生成、来源展示及人工复核整合')
    if ch==2:
        text=re.sub(r'仓库已具备本地技术原型：.*?代码存在不代表学校部署、量表适用性或AI准确性获认证。',
          '现有工程原型已包含学生测评与报告、情绪趋势、求助预约以及教师答复和跟进等页面与接口；教师访问由角色及明确师生分配关系限制。后端具有本地规则分析、结构化报告和本人数据读取路径。这些是可核实的软件基础，量表适配、AI质量及校内流程仍需分别验收。',text)
        text=text.replace('当前门禁记录显示后端135项通过、3项条件跳过及5项WinError10013环境错误；最新真实UI因Vite代理连接EACCES未通过完整集成。上述工程结果支持继续完善原型，不应表述为系统整体集成或AI专业评测已通过。',
          '当前完整整合仍有环境阻塞，具体工程证据与后续修复入口见第5章；真实模型和校内试点尚未验收。')
        text=text.replace('检索增强生成由`backend/app/services/rag_service.py`实现为可选组件：',
                          '检索增强生成（RAG）是通过检索资料为生成内容提供依据的可选组件，当前')
        text=text.replace('`backend/app/routers/llm_gateway.py`当前以本地回退函数生成文本或结构化回退结果',
                          '现有模型网关以本地回退函数生成文本或结构化回退结果')
    if ch==3:
        text=text.replace('需求正从一次性筛查延伸到结果解释、持续关注、人工复核和必要转介。',
                          '本项目关注测评之后的结果说明、持续观察、人工复核和必要转介。')
        text=text.replace('采购公告来源见表3-2','采购公告来源见表4。').replace('不同学段任务及进入条件见表3-3。','不同学段任务及进入条件见表5。')
        text=text.replace('## 表3-1',
          '## 3.4 市场结构与差异化选择\n\n公开案例呈现出单项测评软件、高校综合系统、区域测评与专业服务等交付形态[5]—[8]。这些案例为采购范围分类提供依据，并不代表完整竞争格局。项目首期选择高校中可明确授权和人工承接的具体流程，通过现有系统适配能力、任务完成证据和维护责任争取进入条件，而不以学校总量直接推算订单。\n\n作为方案比较，人工台账便于沿用既有工作习惯，但跨角色记录衔接仍需人工维护；单项测评工具主要承担施测与计分任务，后续服务取决于实际配置；通用对话工具可辅助文字处理，却需要另行建立校内身份、数据范围和审核流程。本项目拟将测评记录、可复算统计、受控知识摘要与人工答复串联，保留每一步来源和处理状态。上述比较是产品任务分析，不是对特定竞品功能或市场占有率的调查结论；差异化价值应在获批验证中以任务耗时、来源核验、人工修订和承接记录检验。\n\n## 表3-1')
        # Keep the two quantitative exhibits near the paragraphs that interpret them.
        main,education=text.split('## 表3-1',1)
        education,procurement=education.split('## 表3-2',1)
        procurement,segments=procurement.split('## 表3-3',1)
        main=main.replace('## 3.2', '## 表3-1'+education+'\n\n## 3.2')
        main=main.replace('## 3.4', '## 表3-2'+procurement+'\n\n## 3.4')
        text=main+'\n\n## 表3-3'+segments
    if ch==5:
        text=text.replace('统计输出应与模型生成解释分栏保存','统计输出应与模型整理的文字草稿分栏保存')
        text=text.replace('模型生成解释和人工确认状态','模型文字草稿和人工确认状态')
        text=text.replace('当前工程回归证据为',
          '现有原型还包含未经临床验证的风险等级、置信字段和关键词固定分值回退。部分报告候选路径会将最近对话片段拼入提示，并可在配置外部地址后发送；不能据此认定已完成去标识处理或具有风险判断效能。未来接入须先审查并限制或整改直接传送原文的路径，将专业判断与现实处置交由授权人员。申报中的目标边界不代表这些既有路径已经整改完成。\n\n当前工程回归证据为')
    return text

def clean(text):
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'[{URLREF[m[2]]}]' if m[2] in URLREF else m[1],text)
    return text.replace('**','').replace('`','').strip()

def header_footer(doc):
    for section in doc.sections:
        for part in (section.header,section.footer):
            for p in part.paragraphs:
                for c in list(p._p):
                    if c.tag!=qn('w:pPr'):p._p.remove(c)
        p=section.header.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        pf.set_run_font(p.add_run('心域智链AI+校园心理支持协作平台项目申报书'),size=9)
        p=section.footer.paragraphs[0];p.alignment=WD_ALIGN_PARAGRAPH.CENTER
        fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');p._p.append(fld)
    for node in list(doc.styles.element.xpath('.//w:pBdr')):node.getparent().remove(node)

def centered_table(doc,rows):
    t=pf.three_line_table(doc,rows)
    t.autofit=False
    widths=[2.3,4.2,4.4,3.6] if len(rows[0])==4 else [3.1,5.7,5.7] if len(rows[0])==3 else [4.0,10.5]
    for c,width in enumerate(widths):t.columns[c].width=Cm(width)
    for r,row in enumerate(t.rows):
        rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))
        if r==0:rp.append(OxmlElement('w:tblHeader'))
        for c,cell in enumerate(row.cells):
            cell.width=Cm(widths[c]);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.line_spacing=1.1;p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
                if r==0:p.paragraph_format.keep_with_next=True
                for run in p.runs:pf.set_run_font(run,size=10.5,bold=r==0)
            if r==0:
                b=cell._tc.get_or_add_tcPr().find(qn('w:tcBorders'))
                b.find(qn('w:bottom')).set(qn('w:sz'),'6')
    return t

def build(output,final=False):
    if output.exists():raise ValueError('Use a new draft path')
    template_hash=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()
    if template_hash!=TEMPLATE_SHA256:raise ValueError('Source attachment changed; inspect before reuse')
    doc=pf.new_document(template_path=TEMPLATE,preserve_template_content=True);front_matter(doc);header_footer(doc)
    for level in [1,2,3]:
        name=f'Heading {level}'
        if name not in doc.styles:
            s=doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH);s.base_style=doc.styles['Normal']
            outline=OxmlElement('w:outlineLvl');outline.set(qn('w:val'),str(level-1));s.element.get_or_add_pPr().append(outline)
    for name in ['Title','Heading 1','Heading 2','Heading 3','Header','Footer']:
        if name in doc.styles:
            doc.styles[name].font.color.rgb=RGBColor(0,0,0)
    title=doc.paragraphs[-1];title.text='心域智链AI+校园心理支持协作平台项目申报书';title.style='Title';title.paragraph_format.page_break_before=True;title.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:pf.set_run_font(run,'黑体',14);run.font.color.rgb=RGBColor(0,0,0)
    pf.abstract_title(doc);pf.body(doc,ABSTRACT);pf.keywords(doc,'高校心理测评；授权持续监测；AI数据分析；大模型协作；人工复核')
    table_number=0;figure_number=0;md=['# 心域智链AI+校园心理支持协作平台项目申报书','','> owner: A ｜ version: 2.0 ｜ status: 图表增强评审稿，真实字段待填写 ｜ updated: 2026-10-27','','## 摘要','',ABSTRACT,'']
    manifest=json.loads((SOURCE/'visual-manifest.json').read_text(encoding='utf-8'))
    figs={f['id']:f for f in manifest['figures']}
    if final and not figs['fig05-mindmap'].get('userStyleApproved'):
        raise ValueError('Final delivery requires the user-reviewed HTML diagram style')
    def table(rows,title):
        nonlocal table_number
        table_number+=1
        p=pf.body(doc,f'相关数据与范围见表{table_number}。');p.paragraph_format.keep_with_next=True
        p=pf.figure_caption(doc,f'表{table_number} {title}');p.paragraph_format.keep_with_next=True
        centered_table(doc,[[clean(v) for v in row] for row in rows])
        md.extend([f'表{table_number} {title}','','| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |'])
        md.extend('| '+' | '.join(row)+' |' for row in rows[1:]);md.append('')
    def figure(id):
        nonlocal figure_number
        figure_number+=1;f=figs[id]
        p=pf.body(doc,f'如图{figure_number}所示，{f["title"]}。');p.paragraph_format.keep_with_next=True
        p=pf.image(doc,SOURCE/f['png'],width_cm=14.5);p.paragraph_format.keep_with_next=True
        p=pf.figure_caption(doc,f'图{figure_number} {f["title"]}');p.paragraph_format.keep_with_next=True
        refs=[URLREF[manifest['sources'][s]['url']] for s in f['sources']]
        caption='来源：'+''.join(f'[{n}]' for n in refs)+'。'+f['scope'] if refs else '项目方案示意，依据当前代码核对与拟建设任务，不表示功能或效果已通过验收。'
        p=pf.paragraph(doc,caption);pf.set_run_font(p.runs[0],size=9)
        md.extend([f'图{figure_number} {f["title"]}',f'![{f["title"]}](ai-application/{f["png"]})',caption,''])
    for ch,title in enumerate(TITLES,1):
        p=pf.heading1(doc,f'{ch} {title}');p.style='Heading 1';p.paragraph_format.keep_with_next=True
        p.paragraph_format.page_break_before=ch==1;p.paragraph_format.space_before=Pt(16);p.paragraph_format.space_after=Pt(8)
        md.extend([f'## {ch} {title}',''])
        text=harmonize((SOURCE/f'chapter-{ch:02d}.md').read_text(encoding='utf-8-sig'),ch)
        if ch==1:text=text.split('### 图表建议')[0]
        lines=text.splitlines();i=0;paragraph_count=0;table_count=0;sub=0;pending_title='本章任务与证据'
        while i<len(lines):
            line=lines[i].strip()
            if not line or line.startswith('>') or line.startswith('# ') or line.startswith('## 一、'):i+=1;continue
            if line.startswith('|'):
                rows=[]
                while i<len(lines) and lines[i].strip().startswith('|'):
                    vals=[v.strip() for v in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-{3,}:?',v) for v in vals):rows.append(vals)
                    i+=1
                if ch==1:
                    vals={m['indicator']:m['value'] for m in manifest['metrics'] if m['source']=='service'}
                    rows[-1]=['2024本科生调查；60,782份有效问卷','知晓学校免费咨询；曾经使用',
                      f"{vals['知晓学校免费心理咨询']:.1f}%；{vals['曾使用学校免费心理咨询']:.1f}%",'两个不同问题，不计算转化率；不外推全国 [3]']
                table(rows,pending_title);table_count+=1
                if ch==3 and table_count==1:figure('fig03-education')
                if ch==3 and table_count==2:figure('fig04-procurement')
                continue
            if line.startswith('#'):
                heading=clean(line.lstrip('#').strip())
                if heading.startswith('表'):
                    pending_title=re.sub(r'^表\d+[-－]\d+\s*','',heading);i+=1;continue
                sub+=1;heading=re.sub(r'^\d+\.\d+\s*','',heading);heading=re.sub(r'^（[^）]+）\s*','',heading)
                heading=heading.replace('：',' ')
                p=pf.heading2(doc,f'{ch}.{sub} {heading}');p.paragraph_format.keep_with_next=True
                p.style='Heading 2'
                md.extend([f'### {ch}.{sub} {heading}','']);pending_title=heading;i+=1;continue
            if line.startswith(('建议架构图：','建议AI调用流程图：')):i+=1;continue
            paragraph_count+=1
            line=clean(re.sub(r'^[-*] ','',line));pf.body(doc,line);md.extend([line,'']);i+=1
            if ch==1 and paragraph_count==1:figure('fig01-youth')
            if ch==1 and paragraph_count==2:figure('fig02-pressure')
            if ch==2 and paragraph_count==3:figure('fig06-architecture')
            if ch==3 and paragraph_count==1:
                p='教育部2025年通报首次全国学生心理健康监测覆盖150万名学生，属于实际监测建设进展[9]；2023—2025专项行动与2026健康学校指导继续部署测评、咨询和监测工具建设[10][11]。这些要求与进展仍需通过学校职责、数据授权、人工服务能力和持续运维落实。'
                pf.body(doc,p);md.extend([p,''])
        if ch==1:
            pf.body(doc,'2024年本科生调查还报告，80.0%的受访者知道学校提供免费心理咨询，2.8%曾实际使用[3]。这两道题分别反映服务知晓与使用经历，不能计算成转化率，也不能将未使用者都视为需要咨询。项目将把求助入口是否易找、告知是否易懂、人工答复是否承接作为后续校内需求核实与可用性验证的问题。')
            figure('fig09-service');figure('fig05-mindmap')
        if ch==5:figure('fig07-ai-workflow')
        # G0—G4 already appear in the native stage table; avoid a redundant final chart page.
    pf.heading1(doc,'参考文献');md.extend(['## 参考文献',''])
    for i,(title,url) in enumerate(REFERENCES,1):
        p=pf.paragraph(doc,f'[{i}] {title}。访问日期2026-10-27。');p.paragraph_format.keep_with_next=True
        for run in p.runs:pf.set_run_font(run,size=10)
        p=pf.paragraph(doc,url)
        for run in p.runs:pf.set_run_font(run,size=8.5)
        md.append(f'[{i}] {title}。{url}\n')
    # Include empty continuation cells of merged source forms, not only row.cells views.
    for tc in doc.element.body.xpath('.//w:tbl//w:tc'):
        cp=tc.get_or_add_tcPr();va=cp.find(qn('w:vAlign'))
        if va is None:va=OxmlElement('w:vAlign');cp.append(va)
        va.set(qn('w:val'),'center')
        for p in tc.findall(qn('w:p')):
            pp=p.get_or_add_pPr();jc=pp.find(qn('w:jc'))
            if jc is None:jc=OxmlElement('w:jc');pp.append(jc)
            jc.set(qn('w:val'),'center')
            for ind in list(pp.findall(qn('w:ind'))):pp.remove(ind)
    for height in doc.element.body.xpath('.//w:trHeight[@w:hRule="exact"]'):
        height.set(qn('w:hRule'),'atLeast')
    # This is an application, not a contest solution: no invented equations or model results.
    # Three retained application forms are unnumbered; body tables/figures checked separately.
    issues=pf.validate_paper_structure(doc,quality_checks=False,min_content_units=10000,min_equations=0,
                                     min_figures=8,min_tables=8,target_pages=0,official_max_pages=100,require_rendered_pages=False)
    QA.mkdir(parents=True,exist_ok=True)
    (QA/'structure-before-render.json').write_text(json.dumps({'issues':issues,'figures':figure_number,'bodyTables':table_number,'retainedForms':3,'status':'final-candidate' if final else 'internal-draft'},ensure_ascii=False,indent=2),encoding='utf-8')
    if issues:raise ValueError('Structure issues: '+'; '.join(issues))
    output.parent.mkdir(parents=True,exist_ok=True)
    # Saving uses the supplied template/style helper; final quality targets above are application-specific.
    doc.save(output)
    (ROOT/'docs/plan/心域智链申报计划书.md').write_text('\n'.join(md),encoding='utf-8')
    assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()==template_hash
    (QA/'build.json').write_text(json.dumps({'output':str(output),'templateSha256':template_hash,'template':str(TEMPLATE),
       'figures':figure_number,'bodyTables':table_number,'retainedForms':3,'final':final,'chapterWriters':[f'chapter_{i:02d}' for i in range(1,7)],'issues':issues},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'figures':figure_number,'tables':table_number,'issues':issues},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--final',action='store_true');a=p.parse_args();build(a.output,a.final)
