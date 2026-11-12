"""Build the revised application: plain prose, regional evidence, notes in appendices."""
import argparse,hashlib,importlib.util,json,re,sys  # noqa: E401, I001
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/plan/ai-application';REV=BASE/'revision-20261027'  # noqa: E702
QA=ROOT/'tmp/application-revision-20261027';QA.mkdir(parents=True,exist_ok=True)  # noqa: E702
spec=importlib.util.spec_from_file_location('legacy_format',ROOT/'scripts/build-ai-application.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)  # noqa: E702
from docx.enum.style import WD_STYLE_TYPE  # noqa: E402, I001
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm,Pt,RGBColor  # noqa: E402

ABSTRACT='心域智链面向高校学生心理测评与后续支持。学生在一次测评之后，还需要看懂记录、找到求助入口；教师则需要在答复和后续沟通中查阅相关资料。项目拟将测评、记录查看、求助预约和教师跟进放在同一平台，在已有前后端基础上完善数据整理和使用流程。AI主要承担资料检索与摘要起草，把记录中的事实、缺失信息和待核对问题分开呈现，由教师核查后使用。项目比较了31个省份的高校和中学在校生规模，并整理地方心理服务建设资料及公开采购案例，以此安排湖北高校的前期调研和产品验证。后续再根据不同学段的工作方式调整初高中版本。预期成果包括软件原型、数据图表、摘要与评测记录，以及培训和运行维护材料。'
FORM_SUMMARY='心域智链面向高校学生心理测评和后续支持，提供测评、记录查看、求助预约及教师答复跟进等功能。项目拟在已有系统基础上完善数据整理，用AI检索资料、起草摘要，帮助教师查看记录和核对问题。申报材料比较31个省份的教育规模，结合地方心理服务建设与采购资料，安排湖北高校的前期调研及产品验证，并为后续初高中版本积累经验。预期形成软件原型、数据图表、评测记录、培训和运行维护材料。'
TITLES=['实用性与创新力','产品与服务','市场分析','推广与实施','方案实现','项目预算与预期成果']
TABLE_TITLES={1:['学生心理与服务调查'],2:['学生与教师的主要使用任务','产品建设安排'],
 3:['2025年高校与初高中教育规模','四项学校心理服务采购案例'],4:['推广与实施安排'],
 5:['AI摘要的拟定结构','现有工程与后续建设'],6:['项目预算科目','阶段任务与交付']}
MOVED=[]

def clean(text):
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',lambda m:f'[{URLREF[m[2]]}]' if m[2] in URLREF else m[1],text).replace('**','').replace('`','').strip()

def prose(raw,ch):
    main,*notes=re.split(r'(?m)^#{1,6}\s*供Lead移入附录的说明\s*$',raw,maxsplit=1)
    main=re.split(r'(?m)^#{1,6}\s*(?:图表建议|来源)\s*$',main)[0]
    if notes:MOVED.append({'chapter':ch,'sourceNotes':notes[0].strip()})  # noqa: E701
    result=[]
    phrases=['不代表','不表示','不等于','不构成','不能替代','不能代替','不能将','不把','不据','不预先','不预设',
      '不能直接照搬','目前没有','当前没有','尚未确定','尚未完成真实模型','没有真实模型效果','未落实','不是诊断','不应把','不外推','不能据此','不是已验证',
      '均待后续填写','均待后期填写','核实后填写','不以推测金额']
    for line in main.splitlines():
        line=line.strip()
        if line.startswith(('>','# 第一章','# 第二章','# 第三章','# 第四章','# 第五章','# 六、','![')):continue  # noqa: E701
        if line.startswith('## 一、'):continue  # noqa: E701
        if line.startswith('#') or line.startswith('|') or line=='{{REGIONAL_COMPARISON}}':result.append(line);continue  # noqa: E701, E702
        if not line:result.append('');continue  # noqa: E701, E702
        if ch==1 and line.startswith('本项目拟将AI用于几项明确'):
            MOVED.append({'chapter':ch,'superseded':line,'reason':'Align AI scope with structured facts and staff review'})
            line='项目拟用统计代码整理测评时间、已确认分数、缺失字段和可比较的变化，结果以图表呈现。大模型接收这些已核对的结构化事实和审核过的参考资料，起草供工作人员复核的短摘要，列出记录要点、资料出处和待确认事项。工作人员对照记录修改草稿，再用于沟通准备。'
        if ch==1 and line.startswith('例如，趋势展示可以提醒'):
            line='例如，同一量表和版本的阶段记录可以并列展示；摘要同时列出所用时间范围、已有信息和资料缺口。工作人员先核对记录，再听取学生对实际经历的说明。资料不足时，摘要保留待确认项，由双方沟通补足背景。学生与工作人员的实际交流，是后续支持的主要依据。'
        if ch==3 and line.startswith('教育资源分布'):
            line='教育部2024年地区统计列出了31个省份的高校和中学生规模，表中同时给出普通、职业高校数量。'
        if ch==6 and line.startswith('每阶段都保存'):
            MOVED.append({'chapter':ch,'detail':line});line='各阶段保存软件和案例版本、检查结果与待处理问题。功能检查主要看权限、答复、跟进和导出能否完成；AI摘要另检查事实、遗漏和教师修改情况。'  # noqa: E702
        kept=[]
        for sentence in re.split(r'(?<=[。！？])',line):
            if any(p in sentence for p in phrases) or (ch!=6 and all(p in sentence for p in ['人员','经费'])):
                if sentence.strip():MOVED.append({'chapter':ch,'detail':sentence})  # noqa: E701
            else:kept.append(sentence)  # noqa: E701
        line=''.join(kept)
        line=line.replace('，而不是把在校生总量直接换算成客户或收入','').replace('；不以学校总量直接推算订单','')
        line=re.sub(r'图3-[12]与表3-[12].*?。','',line)
        line=re.sub(r'表3-2和图3-2.*?。','',line)
        line=line.replace('图表说明或通俗呈现已确认事实','图表说明或简明的事实说明')
        line=line.replace('下一步不是让模型直接“判断学生”，而是把已有记录整理成教师能核对、学生能理解的材料','下一步将把已有记录整理成教师能核对、学生能理解的材料')
        line=line.replace('例如一份摘要可以按以下字段组织，而不是输出一个笼统标签：','摘要拟采用以下结构：')
        if line.strip():result.append(clean(re.sub(r'^[-*]\s+','',line)))  # noqa: E701
    return result

def heading(doc,text,level=1,newpage=False):
    p=b.pf.paragraph(doc,text,align=WD_ALIGN_PARAGRAPH.CENTER if level==1 else None)
    p.style='Heading '+str(level);p.paragraph_format.keep_with_next=True;p.paragraph_format.page_break_before=newpage  # noqa: E702
    p.paragraph_format.space_before=Pt(16 if level==1 else 9);p.paragraph_format.space_after=Pt(8 if level==1 else 4)  # noqa: E702
    for r in p.runs:b.pf.set_run_font(r,size=16 if level==1 else 13,bold=level==1)  # noqa: E701
    return p

def native_table(doc,rows):
    t=b.pf.three_line_table(doc,rows);t.autofit=False  # noqa: E702
    widths={2:[4,10.5],3:[3.1,5.7,5.7],4:[2.8,3.3,3.9,4.5],5:[1.8,2.1,3.6,3.5,3.5]}[len(rows[0])]
    for j,width in enumerate(widths):t.columns[j].width=Cm(width)  # noqa: E701
    for i,row in enumerate(t.rows):
        rp=row._tr.get_or_add_trPr();rp.append(OxmlElement('w:cantSplit'))  # noqa: E702
        if i==0:rp.append(OxmlElement('w:tblHeader'))  # noqa: E701
        for j,c in enumerate(row.cells):
            c.width=Cm(widths[j]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER  # noqa: E702
            for p in c.paragraphs:
                p.alignment=WD_ALIGN_PARAGRAPH.CENTER;p.paragraph_format.line_spacing=1.1  # noqa: E702
                p.paragraph_format.space_before=Pt(3);p.paragraph_format.space_after=Pt(3)  # noqa: E702
                if i==0:p.paragraph_format.keep_with_next=True  # noqa: E701
                for r in p.runs:b.pf.set_run_font(r,size=10.5,bold=i==0)  # noqa: E701
            if i==0:c._tc.get_or_add_tcPr().find(qn('w:tcBorders')).find(qn('w:bottom')).set(qn('w:sz'),'6')  # noqa: E701

regional=json.loads((REV/'regional-education-2024.json').read_text(encoding='utf-8'))
services=json.loads((REV/'regional-services.json').read_text(encoding='utf-8'))['records']
REFERENCES=list(b.REFERENCES)
for source in regional['sources'].values():REFERENCES.append(('教育部 2024年各地区'+source['title'],source['url']))  # noqa: E701
for source in services:REFERENCES.append((source['title'],source['url']))  # noqa: E701
URLREF={url:i for i,(_,url) in enumerate(REFERENCES,1)}

def build(output):
    if output.exists():raise ValueError('Use a new draft output path')  # noqa: E701
    assert hashlib.sha256(b.TEMPLATE.read_bytes()).hexdigest()==b.TEMPLATE_SHA256
    b.FORM_SUMMARY=FORM_SUMMARY
    doc=b.pf.new_document(template_path=b.TEMPLATE,preserve_template_content=True);b.front_matter(doc);b.header_footer(doc)  # noqa: E702
    for level in [1,2,3]:
        name=f'Heading {level}'
        if name not in doc.styles:
            s=doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH);s.base_style=doc.styles['Normal']  # noqa: E702
            o=OxmlElement('w:outlineLvl');o.set(qn('w:val'),str(level-1));s.element.get_or_add_pPr().append(o)  # noqa: E702
    for name in ['Title','Heading 1','Heading 2','Heading 3']:
        if name in doc.styles:doc.styles[name].font.color.rgb=RGBColor(0,0,0)  # noqa: E701
    title=doc.paragraphs[-1];title.text='心域智链AI+校园心理支持协作平台项目申报书';title.style='Title'  # noqa: E702
    title.alignment=WD_ALIGN_PARAGRAPH.CENTER;title.paragraph_format.page_break_before=True  # noqa: E702
    for r in title.runs:b.pf.set_run_font(r,'黑体',14)  # noqa: E701
    b.pf.abstract_title(doc);b.pf.body(doc,ABSTRACT);b.pf.keywords(doc,'高校心理测评；学生支持；地区比较；数据分析；大模型应用')  # noqa: E702
    md=['# 心域智链AI+校园心理支持协作平台项目申报书','','> owner: A ｜ version: 3.0 ｜ status: 文风与地区数据修订审阅稿 ｜ updated: 2026-10-27','','## 摘要','',ABSTRACT,'']
    manifest=json.loads((BASE/'visual-manifest.json').read_text(encoding='utf-8'));figs={f['id']:f for f in manifest['figures']}  # noqa: E702
    table_n=0;figure_n=0;figure_ledger=[]  # noqa: E702
    def paragraph(s):b.pf.body(doc,s);md.extend([s,''])  # noqa: E702
    def table(rows,title):
        nonlocal table_n
        table_n+=1;rows=[[clean(v) for v in row] for row in rows]  # noqa: E702
        p=b.pf.figure_caption(doc,f'表{table_n} {title}');p.paragraph_format.keep_with_next=True  # noqa: E702
        native_table(doc,rows);md.extend([f'表{table_n} {title}','','| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |'])  # noqa: E702
        md.extend('| '+' | '.join(r)+' |' for r in rows[1:]);md.append('')  # noqa: E702
    def figure(id):
        nonlocal figure_n
        figure_n+=1;f=figs[id]  # noqa: E702
        p=b.pf.image(doc,BASE/f['png'],width_cm=14.5);p.paragraph_format.keep_with_next=True  # noqa: E702
        b.pf.figure_caption(doc,f'图{figure_n} {f["title"]}')
        md.extend([f'![{f["title"]}](ai-application/{f["png"]})',f'图{figure_n} {f["title"]}',''])
        figure_ledger.append({'number':figure_n,'id':id,'title':f['title'],'sources':f['sources'],'scope':f['scope']})
    def regions():
        rows=regional['records'];tot=sum(r['normal_vocational_undergraduates'] for r in rows)  # noqa: E702
        table([['地区','普通、职业高校（所）','本专科在校生（万人）','普通高中在校生（万人）','初中在校生（万人）']]+[
          [r['region'],str(r['regular_vocational_heis']),f"{r['normal_vocational_undergraduates']/10000:.2f}",f"{r['regular_senior_students']/10000:.2f}",f"{r['junior_students']/10000:.2f}"] for r in rows],
          '2024年31省份高校与中学教育规模 [12]—[16]')
        top=sorted(rows,key=lambda r:r['normal_vocational_undergraduates'],reverse=True)
        paragraph('从本专科在校生规模看，'+ '、'.join(r['region'] for r in top[:3])+'居前，分别为'+ '、'.join(f"{r['normal_vocational_undergraduates']/10000:.2f}万人" for r in top[:3])+'。图7列出规模前12位的省份，便于比较高校学生群体的分布。')
        figure('fig10-regional-college')
        h=next(r for r in rows if r['region']=='湖北');rank=next(i for i,r in enumerate(top,1) if r['region']=='湖北')  # noqa: E702
        paragraph(f"湖北有普通、职业高校{h['regular_vocational_heis']}所，本专科在校生{h['normal_vocational_undergraduates']/10000:.2f}万人，位列第{rank}，占31省份合计的{h['normal_vocational_undergraduates']/tot*100:.2f}%。普通高中和初中在校生分别为{h['regular_senior_students']/10000:.2f}万人、{h['junior_students']/10000:.2f}万人。项目拟先围绕湖北高校的测评记录、教师答复和后续沟通开展调研，再与周边省市的学校交流使用流程。")
        figure('fig11-hubei-neighbours')
        paragraph('地方学校心理服务建设已有多种做法。武汉报道了心理教师配备情况，广东的项目资金用于心理辅导室建设，嘉兴市南湖区则为新入学随迁子女安排专题活动。其他地区通过指南和标准明确学校应提供哪些服务。')
        sr=[['地区','发布或报告年份','工作内容','已报进展或文件要求']]
        brief=[('湖北省武汉市','2026年报道','中小学专兼职心理教师','报道配备率超过95%'),('广东省项目学校','2024','义务教育心理辅导室建设','项目报告完成64所'),('江苏省','2024','中小学心理辅导室建设','发布省级建设与管理指南'),('浙江省嘉兴市南湖区','2024','新入学随迁子女心理辅导','报道开展20场专题活动'),('山东省','2024','初中心理咨询室装备','指南列明空间、设备与在线系统要求'),('四川省','2026','中小学心理辅导室建设','地方标准于6月29日实施'),('河南省郑州市','2024','义务教育心理支持服务','发布服务规范，规定11月16日起实施'),('北京市','2024发布','中小学心理教师配备','行动计划要求每校至少1名专职教师')]
        for i,row in enumerate(brief):sr.append([*row[:3],row[3]+f' [{17+i}]'])  # noqa: E701
        table(sr,'8个地区学校心理服务建设的公开进展与要求')
    for ch,title_text in enumerate(TITLES,1):
        heading(doc,f'{ch} {title_text}',newpage=ch==1);md.extend([f'## {ch} {title_text}',''])  # noqa: E702
        lines=prose((REV/f'chapter-{ch:02d}.md').read_text(encoding='utf-8-sig'),ch)
        i=0;sub=0;tables=0;paras=0  # noqa: E702
        while i<len(lines):
            line=lines[i].strip();i+=1  # noqa: E702
            if not line:continue  # noqa: E701
            if line=='{{REGIONAL_COMPARISON}}':regions();continue  # noqa: E701, E702
            if line.startswith('|'):
                rows=[]
                while True:
                    vals=[v.strip() for v in line.strip('|').split('|')]
                    if not all(re.fullmatch(r':?-{3,}:?',v) for v in vals):rows.append(vals)  # noqa: E701
                    if i>=len(lines) or not lines[i].strip().startswith('|'):break  # noqa: E701
                    line=lines[i].strip();i+=1  # noqa: E702
                table(rows,TABLE_TITLES[ch][tables]);tables+=1  # noqa: E702
                if ch==2 and tables==1:figure('fig06-architecture')  # noqa: E701
                if ch==3:
                    figure('fig03-education' if tables==1 else 'fig04-procurement')
                    if tables==1:paragraph('学校心理服务的建设也在推进。教育部2025年通报，首次全国学生心理健康监测覆盖150万名学生[9]。2023—2025年专项行动和2026年健康学校建设意见将测评、咨询与服务网络列入学校工作[10][11]。对本项目来说，测评信息需要便于查看和整理，后续沟通也要能连接教师与咨询服务。')  # noqa: E701
                if ch==5 and tables==1:figure('fig07-ai-workflow')  # noqa: E701
                continue
            if line.startswith('#'):
                text=re.sub(r'^\d+\.\d+\s*|^（[^）]+）\s*','',line.lstrip('#').strip());sub+=1  # noqa: E702
                heading(doc,f'{ch}.{sub} {text}',2);md.extend([f'### {ch}.{sub} {text}','']);continue  # noqa: E702
            paragraph(line);paras+=1  # noqa: E702
            if ch==1 and paras in [1,2,3]:figure({1:'fig01-youth',2:'fig02-pressure',3:'fig09-service'}[paras])  # noqa: E701
        if ch==1:figure('fig05-mindmap')  # noqa: E701
    heading(doc,'附录A 数据与图表口径',newpage=True);md.extend(['## 附录A 数据与图表口径',''])  # noqa: E702
    notes=[
      '图示说明：项目方案示意，依据当前代码核对与拟建设任务，不表示功能或效果已通过验收。图4为项目逻辑，图5区分现有工程与拟增强能力，图10为拟建设的AI信息整理流程。',
      '学生调查：图1及表1的风险分组来自抑郁筛查；45.4%指高风险组自陈经常或每天不想上学的比例，无风险组只报告低于5%，未将其绘成精确5%。筛查分组不是临床诊断率，分组关联不能解释为因果关系。[1]',
      '大学生调查：图2四项为2023年大学生竞争感知题项；图3的80.0%与2.8%分别对应知晓免费咨询和曾使用两道题，没有交叉表，不计算转化率，也不将两项视为互斥分布。三项调查的对象和测量不同，不合并成一个总体。[2][3]',
      '全国教育规模：数据来源：[4]。统计不覆盖港澳台。学校和学生规模是潜在服务场景的背景量，不是客户数、需求人数或收入测算基数。2025年高校总数含成人高校，本专科人数不含成人和研究生，不据此计算校均人数。',
      '地区教育规模：31省份比较采用教育部2024年同年表。普通、职业本专科人数为普通本科与职业本专科在校生之和；2870所普通、职业高校不含249所成人高校。高中和初中按学段统计，一贯制等学校相应学段计入。原始单位为人，正文换算为万人并保留两位小数；图7只展示本专科规模前12位，完整31省份见表5。图8包括湖北及河南、安徽、江西、湖南、重庆、陕西，三个面板使用相同单位和横轴范围。[12]—[16]',
      '地方服务资料：表6含3项数值进展、1项标准发布事件与4项指南、标准或计划要求。武汉比例是2026年报道值，具体统计时点和分母未披露，不外推湖北全省；广东64所仅为资金项目覆盖学校；南湖20场是特定群体的活动场次。要求不等于实际建成或覆盖，不将这些异口径资料共轴排名，也不由此推断地区心理问题发生率。[17]—[24]',
      '采购资料：四项2026年公告的成交范围不同。龙泉驿65.3万元包含测评40.7万元和干预24.6万元两包；成都教科院为区域专业服务。成交不等于履约验收、持续使用或服务效果，不据此计算同质均价、每生价格、全国渗透率或本项目收入。项目预算待实际询价及校内核准后填写。[5]—[8]']
    for text in notes:paragraph(text)  # noqa: E701
    heading(doc,'附录B 实施条件与技术现状',newpage=True);md.extend(['## 附录B 实施条件与技术现状',''])  # noqa: E702
    notes=[
      'RAG默认关闭，模型网关当前采用本地回退；报告另有可配置的候选外部模型路径。现有工程包含风险等级、置信字段及关键词固定分值回退；部分报告候选路径会把最近对话片段拼入提示，并可在配置外部地址后发送。它们没有完成真实模型评测，不能把字段名或回退结果当成风险判断效能。正式接入前应审查并限制或整改直接发送原文的路径；正文的建设目标不代表该整改已经完成。',
      '当前工程记录为后端135项通过、3项条件跳过、5项因Windows WinError 10013失败；真实UI整合受Vite代理connect EACCES阻塞，完整集成尚未通过。已有12个合成案例只用于工程演练，没有真实模型输出或临床验证结论。',
      '真实服务前由学校确定量表适用性、资料来源、学生知情与退出方式、人员职责、访问范围、保存和删除办法。外部模型另行确认提供商、精确版本、传输和保存规则、费用及专业审阅。未成年人场景应独立明确适龄工具、监护安排和人工承接，不直接沿用高校方案。',
      '模型只整理已确认事实与审核资料。诊断、量表临床意义解释、危机等级和现实处置由相应专业人员负责。资料不足、检索失败、超时或格式不合格时，显示明确状态并保留人工渠道；不以旧结果或关键词分值冒充本次模型生成。',
      '评价按任务记录完成、耗时、错误、求助和教师修订。任务完成率以启动任务总数为分母，耗时按任务类型报告中位数与范围；AI调用以全部发起调用为总分母，成功、超时、失败、取消分别计数，可评分分母另列。缺失、排除项、版本与评审分歧保留，不把任务体验或合成案例成绩解释为心理改善或临床准确率。',
      '人员、导师、周期、经费及试点信息按负责人核实结果后填。出现未授权访问、无法退出、误导性输出、数据丢失或人工支持无法承接时，按学校预案暂停并复核；生产环境另行检查安全配置、运行维护和异机恢复。']
    for text in notes:paragraph(text)  # noqa: E701
    heading(doc,'参考文献',newpage=True);md.extend(['## 参考文献',''])  # noqa: E702
    for i,(title,url) in enumerate(REFERENCES,1):
        p=b.pf.paragraph(doc,f'[{i}] {title}。访问日期2026-10-27。');p.paragraph_format.keep_with_next=True  # noqa: E702
        for r in p.runs:b.pf.set_run_font(r,size=10)  # noqa: E701
        p=b.pf.paragraph(doc,url)
        for r in p.runs:b.pf.set_run_font(r,size=8.5)  # noqa: E701
        md.extend([f'[{i}] {title}。{url}',''])
    for tc in doc.element.body.xpath('.//w:tbl//w:tc'):
        cp=tc.get_or_add_tcPr();va=cp.find(qn('w:vAlign'))  # noqa: E702
        if va is None:va=OxmlElement('w:vAlign');cp.append(va)  # noqa: E701, E702
        va.set(qn('w:val'),'center')
        for p in tc.findall(qn('w:p')):
            pp=p.get_or_add_pPr();jc=pp.find(qn('w:jc'))  # noqa: E702
            if jc is None:jc=OxmlElement('w:jc');pp.append(jc)  # noqa: E701, E702
            jc.set(qn('w:val'),'center')
            for ind in list(pp.findall(qn('w:ind'))):pp.remove(ind)  # noqa: E701
    for height in doc.element.body.xpath('.//w:trHeight[@w:hRule="exact"]'):height.set(qn('w:hRule'),'atLeast')  # noqa: E701
    output.parent.mkdir(parents=True,exist_ok=True);doc.save(output)  # noqa: E702
    (ROOT/'docs/plan/心域智链申报计划书.md').write_text('\n'.join(md),encoding='utf-8')
    report={'document':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bodyTables':table_n,
      'bodyFigures':figure_n,'references':len(REFERENCES),'regions':31,'serviceRegions':8,'appendices':['A','B'],
      'figureLedger':figure_ledger,'final':False,'sourceChapters':[str(REV/f'chapter-{i:02d}.md') for i in range(1,7)]}
    (QA/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (REV/'editorial-moves.json').write_text(json.dumps({'reason':'User requested plain prose and scope/engineering notes in appendices','moved':MOVED},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['bodyTables','bodyFigures','references','regions','serviceRegions']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();build(a.output)  # noqa: E702
