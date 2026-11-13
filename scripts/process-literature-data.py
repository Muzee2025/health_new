"""Normalize public research aggregates; keep participant rows out of all outputs."""
from __future__ import annotations  # noqa: I001
import csv
import hashlib
import json
import math  # noqa: F401
import re
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document
from pypdf import PdfReader
from lxml import html as lhtml

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/literature-data-20261028'
PUBLIC = ROOT / 'docs/plan/research-data-20261028'
RAW = WORK / 'raw'
NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_xlsx(path):
    """Read cells in memory; caller may emit only schema or aggregate statistics."""
    with zipfile.ZipFile(path) as z:
        strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
        rows = ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('m:sheetData/m:row', NS)
        def value(c):
            if c.get('t') == 'inlineStr':
                s = c.find('m:is',NS)
                return ''.join(s.itertext()) if s is not None else None
            v = c.find('m:v',NS)
            if v is None or v.text in (None,''):
                return None
            if c.get('t') == 's':
                return strings[int(v.text)]
            if c.get('t') == 'e':
                return None
            try:
                n=float(v.text)
                return int(n) if n.is_integer() else n
            except ValueError:
                return v.text
        cells = [{re.sub('[0-9]','',c.get('r')):value(c) for c in row.findall('m:c',NS)} for row in rows]
        headers = cells[0]
        return [headers[k] for k in headers], [{headers[k]:row.get(k) for k in headers} for row in cells[1:] if any(v is not None for v in row.values())]


def save_csv(name, rows):
    if not rows: return  # noqa: E701
    with (PUBLIC/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)  # noqa: E702


def main():
    PUBLIC.mkdir(parents=True, exist_ok=True)
    download=json.loads((WORK/'download-manifest.json').read_text(encoding='utf-8'))
    papers={p['source_id']:p for p in download['papers']}
    assert all(papers[s]['downloads'][0]['status']==200 for s in ['ZHOU2024','CHEN2023','CHEN2021','FENG2025','FITZ2017','YANG2023'])
    result={'owner':'A Lead','version':'1.0','updated':'2026-10-28','scope':'Targeted literature data collection, not a systematic review. Public research aggregates only; not platform users.', 'datasets':{}}
    datasets=result['datasets']
    registry=[]
    metadata={
      'ZHOU2024':(2024,'系统综述与随机效应Meta分析','1988—2024发表；检索截至2024-10-15','中国6—24岁；439项研究',1497524,'多量表；阈值不统一','https://link.springer.com/article/10.1186/s13034-024-00841-w'),
      'CHEN2023':(2023,'单次横断面、整群抽样','以Methods为准；不由发表年份代替调查期','中国自贡中学生',63205,'PHQ-9≥10；GAD-7≥10','https://link.springer.com/article/10.1186/s12888-023-05068-1'),
      'CHEN2021':(2021,'两次独立横断面调查','2020-02-20—27；2020-04-11—19','中国青少年；第二次排除两次均参加者',13440,'CES-D>15；GAD-7>4','https://www.nature.com/articles/s41398-021-01271-4'),
      'YANG2023':(2023,'两阶段横断面；回顾性发病史','2017-10—12','湖南师大新生；筛查6818、分层访谈926',6818,'BDI-II筛查与K-SADS-PL访谈；诊断和筛查分开','https://link.springer.com/article/10.1186/s12888-023-04972-w'),
      'FENG2025':(2025,'随机效应Meta分析','检索截至2024-08-06；以短期终点为主','平均年龄12—25岁；试验数/总样本原文不一致',None,'多种量表；Hedges g正值有利干预','https://www.jmir.org/2025/1/e69639/'),
      'FITZ2017':(2017,'小样本随机对照试验','约2—3周终点','美国年轻成人；70随机，58提供T2',70,'PHQ-9；GAD-7；PANAS','https://mental.jmir.org/2017/2/e19/'),
    }
    for sid,(year,design,period,pop,n,instruments,url) in metadata.items():
        p=papers[sid]
        document=lhtml.fromstring((WORK/p['downloads'][0]['path']).read_bytes(),parser=lhtml.HTMLParser(encoding='utf-8'))
        authors=document.xpath('//meta[@name="citation_author"]/@content')
        if not authors:
            authors=[' '.join(node.itertext()).strip() for node in document.xpath('//article-meta/contrib-group[@content-type="author" or not(@content-type)]/contrib[not(@contrib-type) or @contrib-type="author"]/name')]
        journals=document.xpath('//meta[@name="citation_journal_title"]/@content | //journal-title/text()')
        registry.append({'source_id':sid,'title':p['title'].split(' | ')[0],'authors':'; '.join(authors),'journal':journals[0] if journals else '', 'publication_year':year,'design':design,'observation_period':period,'population':pop,'headline_sample_n':n,'instruments_or_units':instruments,'doi':p['doi'],'article_url':url,'download_url':p['url'],'license':'CC BY 4.0（文章）；具体第三方材料依原文','license_url':'https://creativecommons.org/licenses/by/4.0/','access':'已下载公开原文/表格；YANG个体文件仅本地计算，不分发'})
    datasets['sources']=registry

    # Newly downloaded Zhou supplement, not a copy of the previous workbook.
    supplement=RAW/'ZHOU2024-13034_2024_841_MOESM4_ESM.pdf'
    text='\n'.join(p.extract_text() for p in PdfReader(supplement).pages)
    (WORK/'zhou-supplement-extracted.txt').write_text(text,encoding='utf-8')
    yearly=[];regions=[]  # noqa: E702
    for line in text.splitlines():
        m=re.match(r'^\s*(\d{4})\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+\[([0-9.]+);\s*([0-9.]+)\]\s+(--|\d+%)',line)
        if m:
            year,k,n,p,lo,hi,i2=m.groups()
            yearly.append({'source_id':'ZHOU2024','publication_year':int(year),'studies_k':int(k),'sample_n':int(n),'estimate':float(p),'ci95_lower':float(lo),'ci95_upper':float(hi),'i2':None if i2=='--' else float(i2[:-1])/100,'year_type':'发表年份，非调查年份','source_location':'补充文件4，Table S1，PDF第1页'})
        m=re.match(r'^\s*([A-Za-z ]+?)\s+(\d+)\s+(\d+)\s+([0-9.]+)\s+\[([0-9.]+)-([0-9.]+)\]\s+(--|\d+%)',line)
        if m:
            region,k,n,p,lo,hi,i2=m.groups()
            regions.append({'source_id':'ZHOU2024','subgroup_type':'地区研究亚组','group':region.strip(),'studies_k':int(k),'sample_n':int(n),'estimate':float(p)/100,'ci95_lower':float(lo)/100,'ci95_upper':float(hi)/100,'i2':None if i2=='--' else float(i2[:-1])/100,'instrument':'多量表','cutoff':'不统一','source_location':'补充文件4，Table S2，PDF第2页','limitation':'非省级人群代表率；天津来自多地研究；原表k与正文不一致'})
    assert len(yearly)==31 and len(regions)==33
    datasets['publication_year_groups']=yearly
    screening=[{'source_id':'ZHOU2024','subgroup_type':'总体','group':'全部纳入研究','studies_k':439,'sample_n':1497524,'estimate':.2617,'ci95_lower':.25,'ci95_upper':.2741,'i2':1.0,'instrument':'多量表','cutoff':'不统一','source_location':'摘要/Results','limitation':'合并筛查阳性，不是临床诊断；不能跨重叠亚组相加'}]
    group=''
    for row in papers['ZHOU2024']['tables'][0]['cells'][1:]:
        if len(row)<6: continue  # noqa: E701
        if row[0]: group=row[0]  # noqa: E701
        match=re.search(r'([0-9.]+)\s*\[([0-9.]+)[–-]([0-9.]+)\]',row[4])
        if not match: continue  # noqa: E701
        p,lo,hi=map(float,match.groups())
        screening.append({'source_id':'ZHOU2024','subgroup_type':group,'group':row[1],'studies_k':int(row[2]),'sample_n':int(row[3]),'estimate':p/100,'ci95_lower':lo/100,'ci95_upper':hi/100,'i2':float(row[5].replace('%',''))/100,'instrument':row[1] if group=='Scale' else '多量表','cutoff':'不统一','source_location':'原文Table 1','limitation':'亚组n/k不可相加；保留原文数值'})
    screening.extend(regions)
    for outcome,instrument,p,lo,hi in [('抑郁症状','PHQ-9≥10',.230,.196,.270),('焦虑症状','GAD-7≥10',.139,.112,.170)]:
        screening.append({'source_id':'CHEN2023','subgroup_type':'加权总体','group':outcome,'studies_k':1,'sample_n':63205,'estimate':p,'ci95_lower':lo,'ci95_upper':hi,'i2':None,'instrument':instrument,'cutoff':'>=10','source_location':'Results/摘要','limitation':'自贡单地区横断面；与GAD-7>4的研究不可直接比高低'})
    datasets['screening_aggregates']=screening
    waves=[]
    for wave,start,end,n,dep,dlo,dhi,anx,alo,ahi in [(1,'2020-02-20','2020-02-27',9554,.366,.356,.376,.190,.182,.198),(2,'2020-04-11','2020-04-19',3886,.570,.554,.586,.367,.352,.382)]:
        for outcome,instrument,cutoff,p,lo,hi in [('抑郁症状','CES-D','>15',dep,dlo,dhi),('焦虑症状','GAD-7','>4',anx,alo,ahi)]:
            waves.append({'source_id':'CHEN2021','survey_wave':wave,'start_date':start,'end_date':end,'sample_n':n,'outcome':outcome,'instrument':instrument,'cutoff':cutoff,'estimate':p,'ci95_lower':lo,'ci95_upper':hi,'source_location':'摘要/Results/Table 2','limitation':'两次独立样本；排除重复参加者；不是个体纵向追踪'})
    datasets['survey_waves']=waves

    # Multivariable ORs, preserving reference categories and combined outcome definition.
    factors=[]
    pattern=r'([0-9.]+)\s*\(([0-9.]+)[–-]([0-9.]+),\s*p\s*([<=>]+)\s*([0-9.]+)\)'
    for ti,pop in [(1,'全部中学生'),(2,'初中'),(3,'高中')]:
        factor='';ref=''  # noqa: E702
        for row in papers['CHEN2023']['tables'][ti]['cells'][1:]:
            if len(row)<6: continue  # noqa: E701
            if row[0]: factor=row[0];ref=row[1] if row[5]=='-' else '连续变量每1单位'  # noqa: E701, E702
            m=re.search(pattern,row[5],re.IGNORECASE)
            if m:
                val,lo,hi,op,p=m.groups()
                factors.append({'source_id':'CHEN2023','table':f'Table {ti+1}','population':pop,'outcome':'心理困扰：PHQ-9≥10或GAD-7≥10','factor':factor,'comparison':row[1],'reference':ref,'adjusted_or':float(val),'ci95_lower':float(lo),'ci95_upper':float(hi),'p_reported':op+p,'causal_status':'横断面关联；OR不是风险比','source_cell':row[5]})
    factor='';ref='原文二分类参考'  # noqa: E702
    direct_references={'Second survey completion':'第一次调查','Female':'男性','Senior secondary school':'初中','Major class':'原文未明示参照方向/编码','Participating in distance learning':'不参加远程学习','Concerned about entering a higher grade':'不担忧升学'}
    for row in papers['CHEN2021']['tables'][2]['cells'][3:]:
        if len(row)==1: factor=row[0];ref='';continue  # noqa: E701, E702
        if len(row)<9: continue  # noqa: E701
        if row[1]=='Ref': ref=row[0];continue  # noqa: E701, E702
        if row[0] in direct_references:factor=row[0];ref=direct_references[row[0]]  # noqa: E701, E702
        for offset,outcome in [(1,'CES-D>15'),(5,'GAD-7>4')]:
            try:val,lo,hi=map(float,[row[offset+1],row[offset+2],row[offset+3]])  # noqa: E701
            except ValueError:continue  # noqa: E701
            factors.append({'source_id':'CHEN2021','table':'Table 3','population':'两次独立调查合并','outcome':outcome,'factor':factor or row[0],'comparison':row[0],'reference':ref or '原文对应参考组','adjusted_or':val,'ci95_lower':lo,'ci95_upper':hi,'p_reported':row[offset],'causal_status':'横断面关联；调整后波次OR不是发病率比','source_cell':' | '.join(row)})
    datasets['adjusted_associations']=factors

    # Public participant data are read only in memory. Emit schema/missingness and aggregate design diagnostics.
    columns,rows=read_xlsx(RAW/'YANG2023-12888_2023_4972_MOESM1_ESM.xlsx')
    assert len(rows)==926 and len(columns)==74
    descriptions={'Serial_Number':'研究记录序号，仅作重复性检查，禁止输出值','age':'年龄（岁）','gender':'性别编码；编码本未单独提供','nationality':'民族/国籍原始编码；需核对代码本','Region':'原字段Region；不能直接当省份','grade':'原字段grade；不能直接当年级连续量','BDI_II_Total':'BDI-II总分（0—63）','BDI_II_catigory':'BDI-II分层类别；拼写按原数据保留','date_of_first_filing':'首次填表日期；不导出值','date_of_Interview':'访谈日期；不导出值','Stratum':'两阶段抽样的分层变量','weight':'作者提供的抽样权重；非本轮拟合','gender_weight':'作者提供的性别校准权重；非本轮拟合','psu_college':'院系/抽样单元编码，非真实平台用户ID','Firstonset_age':'首次发作年龄原字段','first_ontset_period':'首次发生时期原字段，保留拼写','treatment':'服务使用编码，未核对编码值','father_education':'父亲教育编码','mother_education':'母亲教育编码','family_pattern':'家庭结构编码','Domestic_Violence':'家庭暴力相关编码','Childhood_abuse':'童年虐待相关编码','MajorLife_events':'重大生活事件编码'}
    dictionary=[]
    for name in columns:
        values=[r[name] for r in rows if r.get(name) not in (None,'')]
        missing=len(rows)-len(values)
        dtype='number' if values and all(isinstance(x,(int,float)) for x in values) else 'text/mixed' if values else 'all missing'
        dictionary.append({'source_id':'YANG2023','variable':name,'description':descriptions.get(name,'原始变量；详细编码未单独提供，不推断其编码含义'),'observed_type':dtype,'sample_rows':len(rows),'nonmissing_n':len(values),'missing_n':missing,'missing_rate':missing/len(rows),'analysis_policy':'排除ID/日期/个人行；仅聚合' if name in ['Serial_Number','date_of_first_filing','date_of_Interview'] else '分层访谈样本；解释需抽样设计与代码本','source_location':'MOESM1_ESM.xlsx，sheet1，首行'})
    datasets['microdata_dictionary']=dictionary
    diag=[]
    def metric(name,value,unit,note):diag.append({'source_id':'YANG2023','metric':name,'value':value,'unit':unit,'interpretation':note})
    metric('访谈记录数',len(rows),'人','分层抽样访谈样本，不是6818筛查人群的简单随机样本')
    metric('原始变量数',len(columns),'列','仅输出字段名和质量聚合，不分发个人行')
    metric('重复研究序号数',len(rows)-len({r['Serial_Number'] for r in rows}),'条','未输出序号')
    bdi=[float(r['BDI_II_Total']) for r in rows if isinstance(r.get('BDI_II_Total'),(int,float))]
    metric('BDI-II总分有值人数',len(bdi),'人','缺失与0分分开')
    metric('访谈样本BDI-II均值',statistics.mean(bdi),'分','未加权，不能外推总体；不解释为诊断率')
    metric('BDI-II超出0—63的人数',sum(v<0 or v>63 for v in bdi),'人','仅量表逻辑范围检查，不用于诊断')
    for name in ['weight','gender_weight']:
        weights=[float(r[name]) for r in rows if isinstance(r.get(name),(int,float))]
        metric(name+'非缺失人数',len(weights),'人','作者权重字段可用性')
        metric(name+'权重和',sum(weights),'权重单位','权重归一化尺度不能代替真实样本数')
        metric(name+'非正值人数',sum(w<=0 for w in weights),'人','加权前设计有效性检查')
        metric(name+'有效样本量近似',sum(weights)**2/sum(w*w for w in weights),'人','Kish近似，仅由权重离散度决定，未考虑整群/分层相关')
    # Validity only, not coding-dependent clinical prevalence estimates.
    for name in ['MDD_lifetime_prevalence','DDysthymic_lifetime_prevalence','mildDD_lifetime_prevalence','MDD_6month','MDD_1month_prevalence','MDD_9month_incidence']:
        metric(name+'非0/1非缺失数',sum(r[name] not in (None,'',0,1) for r in rows),'人','只查二值编码一致性；未重估临床患病率')
    datasets['microdata_quality']=diag

    trial_doc=Document(RAW/'FENG2025-app2.docx')
    trial_rows=[]
    for row in trial_doc.tables[0].rows[1:]:
        c=[' '.join(cell.text.split()) for cell in row.cells]
        def number(x):
            try:return float(x)  # noqa: E701
            except ValueError:return None  # noqa: E701
        trial_rows.append({'source_id':'FENG2025','study':c[0],'sample_type':c[1],'reported_n':int(c[2]),'female_fraction':number(c[3])/100 if number(c[3]) is not None else None,'mean_age':number(c[4]),'agent_name':c[5],'platform':c[6],'mode':c[7],'therapy':c[8],'duration':c[10],'control':c[11],'outcomes':c[12],'source_location':'Multimedia Appendix 2, Table S2','limitation':'按原表15行保留；未把与Woebot单篇重叠样本再次相加'})
    assert len(trial_rows)==15
    datasets['ai_trial_characteristics']=trial_rows
    effects=[]
    effect_cfg=[
      ('抑郁症状','原始合并',10,.50,.18,.82,.897,'<.01','Results: Depression'),
      ('抑郁症状','排除1项异常研究',9,.61,.35,.86,.549,'<.001','Results: Depression sensitivity'),
      ('焦虑症状','原始合并',10,.42,-.04,.87,.874,'.08','Results: Generalized Anxiety'),
      ('焦虑症状','排除1项异常研究',9,.17,-.07,.42,.513,'.17','Results: Generalized Anxiety sensitivity'),
      ('焦虑症状','trim-and-fill校正',None,.06,-.21,.32,None,None,'Results: Generalized Anxiety publication bias'),
      ('压力','原始合并',4,.002,-.19,.20,0.0,'.98','Results: Stress'),
      ('积极情感','原始合并',7,.01,-.24,.27,.631,'.92','Results: Positive Affect'),
      ('消极情感','原始合并',7,.36,-.04,.76,.843,'.08','Results: Negative Affect'),
      ('消极情感','排除异常研究（原文冲突）',10,.11,-.06,.28,.113,'<.001','Results: Negative Affect sensitivity'),
      ('消极情感','trim-and-fill校正',None,.07,-.13,.27,None,None,'Results: Negative Affect publication bias'),
      ('心理幸福感','原始合并',4,.04,-.21,.29,.323,'.76','Results: Mental Well-being'),
    ]
    for outcome,analysis,k,g,lo,hi,i2,p,loc in effect_cfg:
        effects.append({'source_id':'FENG2025','outcome':outcome,'analysis':analysis,'trials_k_reported':k,'hedges_g':g,'ci95_lower':lo,'ci95_upper':hi,'i2':i2,'p_reported':p,'ci_excludes_zero':lo>0 or hi<0,'source_location':loc,'limitation':'正g有利干预；原文报告值，非本项目效果'+('；CI跨0却p<.001、k异常，标为不用于结论' if '冲突' in analysis else '')})
    datasets['ai_effects']=effects
    moderators=[];group=''  # noqa: E702
    for row in papers['FENG2025']['tables'][1]['cells'][1:]:
        if len(row)<=3:group=row[0];continue  # noqa: E701, E702
        m=re.search(r'([0-9.]+)\s*\(([–-]?[0-9.]+) to ([–-]?[0-9.]+)\)',row[3])
        if m:
            g,lo,hi=[float(x.replace('–','-')) for x in m.groups()]
            moderators.append({'source_id':'FENG2025','moderator':group,'category':row[1],'trials_k':int(row[2]),'hedges_g':g,'ci95_lower':lo,'ci95_upper':hi,'source_location':'Table 2','limitation':'跨研究亚组比较，不能认定亚组特征导致疗效差异'})
    datasets['ai_moderators']=moderators
    endpoint=[]
    for row in papers['FITZ2017']['tables'][1]['cells'][2:]:
        if len(row)<8:continue  # noqa: E701
        for arm,offset in [('信息对照',1),('Woebot',3)]:
            mean,se=map(float,re.match(r'([0-9.]+)\s*\(([0-9.]+)\)',row[offset]).groups())
            lo,hi=map(float,re.split('[–-]',row[offset+1]))
            endpoint.append({'source_id':'FITZ2017','outcome':row[0],'arm':arm,'endpoint':'T2；ITT分析','mean':mean,'standard_error':se,'ci95_lower':lo,'ci95_upper':hi,'f_reported':float(row[5]),'p_reported':float(row[6]),'cohen_d_reported':float(row[7]),'source_location':'Table 2；a脚注为pooled mean(SE)','limitation':'SE不是SD；不据此计算原始配对变化；部分原文F/p/CI疑有冲突，未自行修正'})
    datasets['woebot_endpoints']=endpoint

    audits=[
      ('ZHOU2024','发表年份不能当调查年份','Methods明确year of publication；Table S1为31个发表年组','用于文献构成分析，不画作全国年度患病率'),
      ('ZHOU2024','总体与亚组不可相加','地区k合计、学段n总和与总体不同；可能多地/多学段重叠且原文未完全说明','保留原值；不跨亚组相加或重算总体'),
      ('ZHOU2024','青海/西藏研究数在摘要与补充表相反','补充表S2青海1、西藏2；摘要写青海2、西藏1','结构数据以S2为准并保留冲突；不作人群风险排名'),
      ('CHEN2021','两次调查不是同一批人的纵向变化','第二次排除了两波均参加的人；n9554与3886，样本构成不同','20.4/17.7个百分点是样本间筛查比例差'),
      ('CHEN2021','Major class编码含义未明确','表格仅列Major class，没有明确报告参照方向/代码本','保留英文变量名及OR，不自行翻译为重点班或推断编码'),
      ('CHEN2023','回归结局是心理困扰合并结局','Table 2—4的distress为PHQ-9≥10或GAD-7≥10','不能改标为单独抑郁或焦虑的OR；OR不是RR'),
      ('YANG2023','入学筛查与访谈样本不同','6818筛查响应、926分层访谈；原始xlsx只有访谈样本','不把未加权访谈比例当总体患病率'),
      ('YANG2023','SciSpace存储年份与论文年份不同','补充材料库条目2024；主文2023，调查2017','分别存发表/调查/存储年份'),
      ('YANG2023','个体记录不进入交付包','原始补充含ID/日期和健康变量','原xlsx只留tmp，交付74字段质量聚合，不输出个人行'),
      ('YANG2023','BDI-II总分有8条缺失','926条访谈记录中918条总分有值，其余8条缺失；有效分数均在0—63','均值分母使用918，不填0，不据此判定缺失机制'),
      ('YANG2023','权重尺度与有效样本量不同','sampling weight和6819.85；Kish近似有效样本量356.32；gender_weight尺度另不同','使用作者设计说明；不能把权重和当实际人数或直接把性别权重当最终合成权重'),
      ('YANG2023','主文与补充表性别校准值不一致','主文Table2与补充Table S3的部分post-stratification列数值不同','保留待澄清；本轮不自行重估诊断患病率'),
      ('YANG2023','性别标准化未独立复现','按主文58%女性直接标准化不能复现其全部sex-adjusted总体值；与作者校准权重定义可能有关','不重写原表，不把近似尝试作为诊断率结论；需要作者澄清'),
      ('FENG2025','试验数与样本数在文中不一致','Results写15试验/1901；摘要1974，Discussion写16/1974','保留冲突；用15行S2复算，不统一篡改原文总量'),
      ('FENG2025','消极情感敏感性结果自相矛盾','g0.11的CI−0.06至0.28跨0，p<.001，k从7变10','该行只留审计，不用于疗效判断'),
      ('FENG2025','摘要与正文对抑郁校正方法措辞不同','摘要称publication-bias adjustment；正文0.61来自排除异常研究','按正文标为排除异常研究，保留0.50原始合并结果'),
      ('FITZ2017','原表统计量疑有不一致','PANAS negative F0.91/P.912；若干CI与SE不完全对应','按原表列示并标注，不据疑似错误重算疗效'),
      ('SCISPACE','受限数据不当作已获得','Chinese University Students Lifestyle Dataset 35,197记录/82字段需签章申请并有限制','未申请、未解密、未混入可分析数据'),
    ]
    datasets['source_audits']=[dict(zip(['source_id','issue','observed_evidence','handling'],r)) for r in audits]  # noqa: B905
    files=[];seen=set()  # noqa: E702
    for sid,p in papers.items():
        for d in p['downloads']:
            if d.get('status')!=200:continue  # noqa: E701
            f=WORK/d['path'];assert hashlib.sha256(f.read_bytes()).hexdigest()==d['sha256']  # noqa: E702
            if d['sha256'] in seen:continue  # noqa: E701
            seen.add(d['sha256'])
            excluded=f.suffix.lower()=='.xlsx'
            files.append({'source_id':sid,'file':f.name,'sha256':d['sha256'],'bytes':d['bytes'],'url':d['url'],'downloaded_at':d['downloaded_at'],'delivery':'仅本地，含个体数据' if excluded else '研究资料包','license':'CC BY 4.0；数值/表格按原文许可','local_relative_path':d['path']})
    datasets['downloaded_files']=files
    result['microdata']={'source_id':'YANG2023','rows':len(rows),'columns':len(columns),'no_participant_rows_exported':True}
    result['summary']={'unique_downloaded_files':len(files),'sources':len(registry),'year_groups':len(yearly),'region_groups':len(regions),'screening_rows':len(screening),'or_rows':len(factors),'ai_trial_rows':len(trial_rows),'ai_trial_n_sum':sum(x['reported_n'] for x in trial_rows),'microdata_rows':len(rows),'microdata_columns':len(columns),'wave_depression_difference_pp':(.570-.366)*100,'wave_anxiety_difference_pp':(.367-.190)*100}
    for name,values in datasets.items():save_csv(name+'.csv',values)  # noqa: E701
    (PUBLIC/'processed-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'summary':result['summary'],'quality':diag[:14]},ensure_ascii=False))


if __name__=='__main__':main()  # noqa: E701
