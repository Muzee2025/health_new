"""Add reproducible statistics and literature data; use title-free publication figures."""
import argparse,hashlib,importlib.util,json,re  # noqa: E401, I001
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement  # noqa: F401
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: F401
from docx.shared import Pt,RGBColor

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/plan/ai-application'  # noqa: E702
DATA=BASE/'sci-revision-20261027';QA=ROOT/'tmp/sci-application-20261027'  # noqa: E702
spec=importlib.util.spec_from_file_location('application_format',ROOT/'scripts/build-revised-application.py')
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)  # noqa: E702

REGION_EN='Beijing Tianjin Hebei Shanxi Inner_Mongolia Liaoning Jilin Heilongjiang Shanghai Jiangsu Zhejiang Anhui Fujian Jiangxi Shandong Henan Hubei Hunan Guangdong Guangxi Hainan Chongqing Sichuan Guizhou Yunnan Tibet Shaanxi Gansu Qinghai Ningxia Xinjiang'.split()
REGION_ZH='北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏 陕西 甘肃 青海 宁夏 新疆'.split()
STAGES={'Primary school':'小学','Middle school':'初中','High school':'高中','Undergraduate school':'本科'}
CAPTIONS={
 'fig01-youth':'2024年青少年抑郁筛查分组与学习状态。（a）上学意愿；（b）自陈学习行为',
 'fig02-pressure':'2023年大学生学业竞争感知',
 'fig03-education':'2025年高校与中学在校生规模',
 'fig04-procurement':'2026年四项心理服务采购案例。（a）高校软件及系统；（b）区域测评与综合服务',
 'fig05-mindmap':'AI+高校心理测评与持续支持逻辑',
 'fig06-architecture':'系统与AI能力的分层关系',
 'fig07-ai-workflow':'AI分析与大模型的人机协作流程',
 'fig09-service':'2024年大学生免费咨询知晓与使用',
 'fig10-regional-college':'2024年本专科在校生规模前12位省份',
 'fig11-hubei-neighbours':'2024年湖北及周边六省市在校生规模。（a）本专科；（b）普通高中；（c）初中',
 'fig12-literature-stage':'不同学段抑郁症状筛查阳性的合并比例及95%置信区间',
 'fig13-literature-regions':'纳入研究的31省份地区亚组合并比例与95%置信区间',
 'fig14-education-lorenz':'2024年三个学段在校生规模的地区累计份额曲线'}
FORMULAS={
 'share':(r'p_i=\frac{x_i}{S},\quad S=\sum_{i=1}^{n}x_i,\quad n=31','pᵢ = xᵢ / S，S = Σᵢ₌₁ⁿ xᵢ，n = 31'),
 'cv':(r'\mu=\frac{S}{n},\quad \sigma=\sqrt{\frac{1}{n}\sum_{i=1}^{n}(x_i-\mu)^2},\quad CV=\frac{\sigma}{\mu}','μ = S / n，σ = √[Σᵢ₌₁ⁿ (xᵢ − μ)² / n]，CV = σ / μ'),
 'cr5':(r'CR_5=\frac{\sum_{r=1}^{5}x_{(r)}}{S}','CR₅ = Σᵣ₌₁⁵ x₍ᵣ₎ / S'),
 'gini':(r'G=\frac{\sum_{i=1}^{n}\sum_{j=1}^{n}|x_i-x_j|}{2nS}','G = Σᵢ₌₁ⁿ Σⱼ₌₁ⁿ |xᵢ − xⱼ| / (2nS)'),
 'lorenz':(r'L_k=\frac{\sum_{r=1}^{k}x_{[r]}}{S},\quad k=0,1,\ldots,n','Lₖ = Σᵣ₌₁ᵏ x₍升序r₎ / S，k = 0, 1, …, n')}

def mdtable(key,title,rows):
    return '\n\n'+f'表@{key} {title}'+'\n\n'+'\n'.join('| '+' | '.join(r)+' |' for r in [rows[0],['---']*len(rows[0]),*rows[1:]])+'\n\n'

def figure(key):return f'\n\n![{CAPTIONS[key]}](ai-application/figures-sci/{key}.png)\n图@{key} {CAPTIONS[key]}\n\n'

def content(source):
    lit=json.loads((DATA/'literature-data.json').read_text(encoding='utf-8'))
    math=json.loads((DATA/'math-analysis.json').read_text(encoding='utf-8'))
    text=source.read_text(encoding='utf-8')
    text=re.sub(r'> owner: A.*?\n','> owner: A ｜ version: 4.0 ｜ status: 科研图与数学分析修订稿 ｜ updated: 2026-10-27\n',text,count=1)
    # Figure identities are stable; captions are assigned only after all insertions.
    pattern=r'!\[.*?\]\(ai-application/figures/(fig[^)]+)\.png\)\n图\d+[^\n]*'
    previous_ids=re.findall(pattern,text)
    old_figures={i:k for i,k in enumerate(previous_ids,1)}
    text=re.sub(pattern,lambda m:figure(m[1]).strip(),text)
    text=re.sub(r'(?m)^表(\d+)\s',lambda m:'表@old'+m[1]+' ',text)
    stages=lit['study']['education_stage_subgroups']
    block='### 1.2 从多项研究观察学段与地区差异\n\n'
    block+='除单项调查外，Zhou等的综述纳入439项研究、1,497,524名6—24岁参与者，抑郁症状筛查阳性的合并比例为26.17%，95%置信区间为25.00%—27.41%，总体异质性I²=100%。同一综述列出了四个学段，便于把高校需求放在成长阶段中理解。[25]\n'
    rows=[['学段研究亚组','研究数k','样本记录数n','合并比例（%）','95%置信区间（%）']]
    for r in stages:rows.append([STAGES[r['stage']],str(r['studies_k']),f"{r['sample_n']:,}",f"{r['estimate_percent']:.2f}",f"{r['ci95_lower_percent']:.2f}—{r['ci95_upper_percent']:.2f}"])  # noqa: E701
    block+=mdtable('stage','文献学段亚组的抑郁症状筛查结果 [25]',rows)+figure('fig12-literature-stage')
    block+='高中和本科亚组的点估计分别为28.23%和27.72%，初中为24.15%，小学为16.97%。高中与小学点估计相差11.26个百分点。初高中阶段的学习适应和进入大学后的生活转变，都应在测评反馈与后续支持中有所体现。\n\n'
    block+='地区亚组呈现了另一层差异。下表按教育部地区顺序列出31省份的研究汇总，每行同时给出研究数、样本记录数和区间。项目调研将结合湖北高校的具体流程，了解不同学校怎样组织测评、解释记录和承接学生求助。[26]\n'
    index={r['region']:r for r in lit['geographic_subgroups']['rows']}
    rows=[['地区研究亚组','研究数k','样本记录数n','合并比例（%）','95%置信区间（%）']]
    for en,zh in zip(REGION_EN,REGION_ZH):  # noqa: B905
        r=index[en.replace('_',' ')]
        rows.append([zh+('（含多地）' if zh=='天津' else ''),str(r['studies_k']),f"{r['sample_n']:,}",f"{r['estimate_percent']:.2f}",f"{r['ci95_lower_percent']:.2f}—{r['ci95_upper_percent']:.2f}"])
    block+=mdtable('literature-regions','31省份文献地区亚组的抑郁症状筛查结果 [26]',rows)+figure('fig13-literature-regions')
    text=text.replace('### 1.2 让测评成为沟通的起点',block+'### 1.2 让测评成为沟通的起点')
    stats=math['stage_statistics']
    block='### 3.3 教育规模的数学分析\n\n'
    block+='把同一学段第i个地区的在校生数记为xᵢ，31个地区合计为S。地区占比pᵢ用于判断学生群体的分布；均值和中位数描述典型规模，变异系数CV衡量相对离散程度。\n\n{{EQ:share}}\n\n{{EQ:cv}}\n'
    rows=[['学段','合计（万人）','均值（万人）','中位数（万人）','总体SD（万人）']]
    for stage,s in stats.items():rows.append([stage]+[f"{s[k]/10000:.2f}" for k in ['total','mean','median','population_sd']])  # noqa: E701
    block+=mdtable('descriptive','2024年31省份教育规模的描述统计',rows)
    block+='三个学段的均值都高于中位数，表明少数规模较大的地区提高了均值。以初中为例，地区均值为173.75万人、中位数为145.15万人；本专科地区均值为125.52万人、中位数为114.96万人。比较调研地区时，同时看规模和分布，比只看全国总量更有用。\n\n'
    block+='再将各地区人数从大到小排列为x₍ᵣ₎，前五地区份额CR₅反映人数最多五地占合计的比例。基尼系数G则汇总31个地区之间的人数差异。\n\n{{EQ:cr5}}\n\n{{EQ:gini}}\n'
    rows=[['学段','CV（%）','前五份额CR₅（%）','基尼系数G']]
    for stage,s in stats.items():rows.append([stage,f"{s['cv']*100:.2f}",f"{s['cr5']*100:.2f}",f"{s['gini']:.4f}"])  # noqa: E701
    block+=mdtable('concentration','2024年三个学段教育规模的地区集中程度',rows)+figure('fig14-education-lorenz')
    block+='本专科、普通高中和初中的前五地区份额分别为34.01%、36.34%和38.02%，基尼系数依次为0.3545、0.3934和0.4122。初中规模在地区之间更集中，本专科分布相对分散。对本项目而言，先在湖北高校观察完整使用流程，再比较不同规模学校的组织方式，有助于安排后续调研范围。\n\n'
    text=text.replace('### 3.3 采购案例与产品切入',block+'### 3.3 采购案例与产品切入')
    extraA='\n\n文献数据：[25]检索截止2024年10月15日，纳入研究发表年份为1988—2024，现场调查时点不统一。不同量表和阈值并存，总体I²=100%，作者报告发表偏倚。各学段及地区亚组的k和n不是互斥分层，不能相加；所有比例和95%置信区间直接摘录原文，没有重新合并或换算全国患者人数。点估计差11.26个百分点只是描述差，未追加两两显著性检验。\n\n'
    extraA+='地区文献表和图按[26]的Table S2列值，正文只展示大陆31省份，原表另外含香港、台湾两行。单研究地区用空心点表示；天津来自含天津的多地研究，表中注明“含多地”。原摘要对青海、西藏研究数的排列与S2相反，本文按明细表采用青海k=1、西藏k=2，保留这一原文不一致。地区亚组不等于省级代表性人群风险率，不能按这些合并比例推算服务人数或订单。\n\n'
    extraA+='制图处理：原调查只报告无风险组“不想上学”低于5%，未提供精确点值，故不以5%绘柱。将该比例记为p₀，0≤p₀<0.05，则0.454−p₀>0.404，即与高风险组的差值严格大于40.4个百分点。分组样本分母缺失，不构造这一差值的置信区间、显著性或因果结论。\n\n'
    text=text.replace('## 附录B 实施条件与技术现状',extraA+'## 附录B 实施条件与技术现状')
    appendix='## 附录C 数学方法与图形规范\n\n'
    appendix+='教育规模统计使用31地完整行政统计横截面。SD以n=31为分母，CV为SD除以均值；CR₅按各学段各自人数最多五地计算。G采用两两绝对差公式，并以排序加权公式独立复算。Q1、Q3采用h=(n−1)p的线性插值；完整未舍入结果及31地派生占比、名次和每校规模在分析数据文件中保存。\n\n'
    appendix+='累计份额曲线对每个学段分别升序排列x，横轴为地区累计份额k/n，纵轴为在校生累计份额Lₖ；曲线与45度线的偏离用于描述地区分布。\n\n{{EQ:lorenz}}\n\n'
    appendix+='这些计算描述教育规模分布，不测量心理风险、服务缺口、付费意愿或收入。各学段不作为同一学生队列的升学转化，未作回归、预测或显著性推断。不同来源的筛查研究也未和教育人数相乘。\n\n'
    appendix+='图形采用通用科学期刊规范：145毫米文档宽度、无图内总标题、统一字体与线宽、坐标标明指标和单位，来源与处理解释集中在附录。数据图保留真实原值与原文区间；颜色配合线型、点型或纹理，便于灰度阅读。成图导出600DPI PNG、可编辑文字SVG和字体嵌入PDF；中文标签使用宋体，西文与数字使用Arial。参照Nature公开图形说明[27]，未声称已通过某期刊审稿。\n\n'
    text=text.replace('## 参考文献',appendix+'## 参考文献')
    refs=[('Zhou J, Liu Y, Ma J, et al. Prevalence of depressive symptoms among children and adolescents in China: a systematic review and meta-analysis. 2024;18:150.','https://link.springer.com/article/10.1186/s13034-024-00841-w'),
      ('Zhou等. Additional file 4, Table S2 地区亚组明细.','https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs13034-024-00841-w/MediaObjects/13034_2024_841_MOESM4_ESM.pdf'),
      ('Nature. Final submission: final print-only artwork.','https://www.nature.com/nature/for-authors/final-submission')]
    text+='\n\n'+'\n\n'.join(f'[{n}] {title} {url}' for n,(title,url) in enumerate(refs,25))+'\n'
    # Resolve original figure/table cross-references after inserting new assets.
    for kind in ['表','图']:
        tokens=re.findall(r'(?m)^'+kind+r'@([\w-]+) ',text);mapping={token:i for i,token in enumerate(tokens,1)}  # noqa: E702
        oldmap={int(k[3:]):v for k,v in mapping.items() if k.startswith('old')} if kind=='表' else {n:mapping[k] for n,k in old_figures.items()}
        # The two lambdas below close over `kind`/`oldmap`/`mapping` from the loop.
        # `re.sub` consumes them synchronously inside the same iteration, so the
        # late binding never triggers today. Verified with a minimal repro: the
        # same pattern returns wrong values only if the closure is stored and
        # called after the loop. Bind defaults (lambda m, k=kind: ...) if this is
        # ever refactored to defer the call.
        text=re.sub(kind+r'(\d+)(?!\d)',lambda m:kind+str(oldmap.get(int(m[1]),int(m[1]))),text)  # noqa: B023
        text=re.sub(kind+r'@([\w-]+)',lambda m:kind+str(mapping[m[1]]),text)  # noqa: B023
    # Regenerate subsection numbers in reading order.
    chapter=0;counts={}  # noqa: E702
    lines=[]
    for line in text.splitlines():
        if re.match(r'^## [1-6] ',line):chapter=int(line[3]);counts[chapter]=0  # noqa: E701, E702
        if re.match(r'^### [1-6]\.\d+ ',line):
            counts[chapter]+=1;line=re.sub(r'^### \d+\.\d+ ',f'### {chapter}.{counts[chapter]} ',line)  # noqa: E702
        lines.append(line)
    return '\n'.join(lines)+'\n'

def build(source,base_docx,output):
    if output.exists():raise ValueError('Use a new candidate output path')  # noqa: E701
    md=content(source);doc=Document(base_docx)  # noqa: E702
    title=next(p for p in doc.paragraphs if p.style.name=='Title' and '项目申报书' in p.text)
    cursor=title._p.getnext()
    while cursor is not None:
        nxt=cursor.getnext()
        if cursor.tag!=qn('w:sectPr'):cursor.getparent().remove(cursor)  # noqa: E701
        cursor=nxt
    lines=md.splitlines();i=0;equations=0;images=[];tables=0;abstract=False  # noqa: E702
    while i<len(lines):
        line=lines[i].strip();i+=1  # noqa: E702
        if not line or line.startswith(('# ','>')):continue  # noqa: E701
        if line.startswith('## 摘要'):g.b.pf.abstract_title(doc);abstract=True;continue  # noqa: E701, E702
        if line.startswith('## '):
            if abstract:g.b.pf.keywords(doc,'高校心理测评；地区比较；描述统计；数据分析；大模型应用');abstract=False  # noqa: E701, E702
            value=line[3:];g.heading(doc,value,newpage=value.startswith(('1 ','附录','参考文献')));continue  # noqa: E702
        if line.startswith('### '):g.heading(doc,line[4:],2);continue  # noqa: E701, E702
        if line.startswith('表') and re.match(r'^表\d+ ',line):
            p=g.b.pf.figure_caption(doc,line);p.paragraph_format.keep_with_next=True;continue  # noqa: E702
        if line.startswith('|'):
            rows=[]
            while True:
                row=[c.strip() for c in line.strip('|').split('|')]
                if not all(re.fullmatch(':?-{3,}:?',c) for c in row):rows.append(row)  # noqa: E701
                if i>=len(lines) or not lines[i].strip().startswith('|'):break  # noqa: E701
                line=lines[i].strip();i+=1  # noqa: E702
            g.native_table(doc,rows);tables+=1;continue  # noqa: E702
        match=re.fullmatch(r'!\[.*?\]\(([^)]+)\)',line)
        if match:
            file=ROOT/'docs/plan'/match[1];assert file.exists()  # noqa: E702
            p=g.b.pf.image(doc,file,width_cm=14.5);p.paragraph_format.keep_with_next=True;images.append(file.name);continue  # noqa: E702
        if re.match(r'^图\d+ ',line):g.b.pf.figure_caption(doc,line);continue  # noqa: E701, E702
        match=re.fullmatch(r'\{\{EQ:(\w+)\}\}',line)
        if match:
            equations+=1;p=g.b.pf.equation(doc,FORMULAS[match[1]][0]);p.paragraph_format.space_before=Pt(5);p.paragraph_format.space_after=Pt(5)  # noqa: E702
            p.add_run(f'  （{equations}）');continue  # noqa: E702
        if re.match(r'^\[\d+\]',line):
            title_text,url=line.rsplit(' ',1) if ' https://' in line else (line,'')
            # Previous source lines separate Chinese title from URL with a full stop.
            hit=re.search(r'https://\S+',line)
            if hit:title_text=line[:hit.start()].rstrip('。 ');url=hit[0]  # noqa: E701, E702
            p=g.b.pf.paragraph(doc,title_text+'。访问日期2026-10-27。');p.paragraph_format.keep_with_next=True  # noqa: E702
            for run in p.runs:g.b.pf.set_run_font(run,size=10)  # noqa: E701
            p=g.b.pf.paragraph(doc,url)
            for run in p.runs:g.b.pf.set_run_font(run,size=8.5)  # noqa: E701
            continue
        g.b.pf.body(doc,line)
    for name in ['Title','Heading 1','Heading 2','Heading 3']:doc.styles[name].font.color.rgb=RGBColor(0,0,0)  # noqa: E701
    for height in doc.element.body.xpath('.//w:trHeight[@w:hRule="exact"]'):height.set(qn('w:hRule'),'atLeast')  # noqa: E701
    doc.save(output)
    for number,(key,(_,display)) in enumerate(FORMULAS.items(),1):md=md.replace('{{EQ:'+key+'}}','$$'+display+f'  （{number}）$$')  # noqa: E701
    (ROOT/'docs/plan/心域智链申报计划书.md').write_text(md,encoding='utf-8')
    report={'document':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
      'baseSourceSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'baseDocxSha256':hashlib.sha256(base_docx.read_bytes()).hexdigest(),
      'bodyTables':tables,'bodyFigures':len(images),'figureFiles':images,'nativeEquations':equations,'references':27,'educationRegions':31,'literatureRegions':31,'originalLiteratureRegions':33}
    QA.mkdir(parents=True,exist_ok=True);(QA/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')  # noqa: E702
    print(json.dumps({k:v for k,v in report.items() if k not in ['figureFiles','baseSourceSha256','baseDocxSha256']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)  # noqa: E702
    p.add_argument('--base-docx',type=Path,required=True);p.add_argument('--output',type=Path,required=True)  # noqa: E702
    a=p.parse_args();build(a.source,a.base_docx,a.output)  # noqa: E702
