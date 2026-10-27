"""Read-only checks for title-free figures, native mathematics and source tables."""
import argparse,hashlib,json,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'docs/plan/ai-application/sci-revision-20261027'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
W='{'+NS['w']+'}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def txt(e):return ''.join(e.xpath('.//w:t/text()',namespaces=NS))
def verify(docx,render,report,delivery=None,browser_report=None,page_review=None,review_report=None):
    original=Path('C:/University/Files/附件.docx')
    assert sha(original)=='2531a2432493e4592d0759473fb3add5b6e1770e3c69ef1ee501d31b1943202a'
    with ZipFile(docx) as z,ZipFile(original) as oz:
        tree=etree.fromstring(z.read('word/document.xml'));old=etree.fromstring(oz.read('word/document.xml'))
        tables=tree.findall('.//w:tbl',NS);assert len(tables)==19
        for a,b in zip(tables[:3],old.findall('.//w:tbl',NS)):
            for tag in ['tr','gridSpan','vMerge']:
                aa=a.findall('.//w:'+tag,NS);bb=b.findall('.//w:'+tag,NS);assert len(aa)==len(bb)
                if tag!='tr':assert [x.attrib for x in aa]==[x.attrib for x in bb]
        assert sum(txt(t).count('【待填写】') for t in tables[:3])==42
        assert txt(tables[17]).count('【后期手动填写】')==7
        table_checks=[]
        for ti,t in enumerate(tables):
            rows=t.findall('w:tr',NS);header=2 if ti==0 else 0
            allowed={(0,'top'),(header,'bottom'),(len(rows)-1,'bottom')};rules=set()
            for border in t.findall('w:tblPr/w:tblBorders/*',NS):
                side=etree.QName(border).localname;v=border.get(W+'val')
                if v not in ('nil','none'):
                    assert side in ('top','bottom') and v=='single' and border.get(W+'sz')=='12'
                    rules.add((0 if side=='top' else len(rows)-1,side))
            for ri,row in enumerate(rows):
                for c in row.findall('w:tc',NS):
                    assert c.find('w:tcPr/w:vAlign',NS).get(W+'val')=='center'
                    for p in c.findall('w:p',NS):assert p.find('w:pPr/w:jc',NS).get(W+'val')=='center'
                    for b in c.findall('w:tcPr/w:tcBorders/*',NS):
                        side=etree.QName(b).localname;v=b.get(W+'val')
                        if v not in ('nil','none'):
                            assert (ri,side) in allowed and v=='single'
                            assert b.get(W+'sz')==('6' if (ri,side)==(header,'bottom') else '12')
                            rules.add((ri,side))
            assert rules==allowed,(ti,rules)
            table_checks.append({'table':ti+1,'rows':len(rows),'threeLines':True,'centered':True})
        paras=[txt(p) for p in tree.findall('.//w:body/w:p',NS)]
        for kind,n in [('图',13),('表',16)]:
            assert [int(re.match('^'+kind+r'(\d+) ',p)[1]) for p in paras if re.match('^'+kind+r'\d+ ',p)]==list(range(1,n+1))
        assert len(tree.findall('.//w:drawing',NS))==14
        assert len(tree.findall('.//m:oMathPara',NS))==5
        assert len(tree.findall('.//w:sectPr',NS))==3
        assert [int(re.match(r'^\[(\d+)\]',p)[1]) for p in paras if re.match(r'^\[\d+\]',p)]==list(range(1,28))
        lit=json.loads((DATA/'literature-data.json').read_text(encoding='utf-8'))
        rows=tables[4].findall('w:tr',NS);assert len(rows)==5
        for row,r in zip(rows[1:],lit['study']['education_stage_subgroups']):
            values=[txt(c) for c in row.findall('w:tc',NS)]
            assert values[1:]==[str(r['studies_k']),f"{r['sample_n']:,}",f"{r['estimate_percent']:.2f}",f"{r['ci95_lower_percent']:.2f}—{r['ci95_upper_percent']:.2f}"]
        rows=tables[5].findall('w:tr',NS);assert len(rows)==32
        assert '天津（含多地）' in txt(rows[2])
        en='Beijing Tianjin Hebei Shanxi Inner_Mongolia Liaoning Jilin Heilongjiang Shanghai Jiangsu Zhejiang Anhui Fujian Jiangxi Shandong Henan Hubei Hunan Guangdong Guangxi Hainan Chongqing Sichuan Guizhou Yunnan Tibet Shaanxi Gansu Qinghai Ningxia Xinjiang'.split()
        index={r['region']:r for r in lit['geographic_subgroups']['rows']}
        for row,name in zip(rows[1:],en):
            r=index[name.replace('_',' ')];values=[txt(c) for c in row.findall('w:tc',NS)]
            assert values[1:]==[str(r['studies_k']),f"{r['sample_n']:,}",f"{r['estimate_percent']:.2f}",f"{r['ci95_lower_percent']:.2f}—{r['ci95_upper_percent']:.2f}"]
        assert len(tables[9].findall('w:tr',NS))==32
        assert len(tables[10].findall('w:tr',NS))==9
        stats=json.loads((DATA/'math-analysis.json').read_text(encoding='utf-8'))['stage_statistics']
        for row,(stage,s) in zip(tables[11].findall('w:tr',NS)[1:],stats.items()):
            assert [txt(c) for c in row.findall('w:tc',NS)]==[stage]+[f"{s[k]/10000:.2f}" for k in ['total','mean','median','population_sd']]
        for row,(stage,s) in zip(tables[12].findall('w:tr',NS)[1:],stats.items()):
            assert [txt(c) for c in row.findall('w:tc',NS)]==[stage,f"{s['cv']*100:.2f}",f"{s['cr5']*100:.2f}",f"{s['gini']:.4f}"]
    md=(ROOT/'docs/plan/心域智链申报计划书.md').read_text(encoding='utf-8')
    main,appendix=md.split('## 附录A',1)
    assert not any(p in main for p in ['来源：','不作精确柱值','不以5%绘柱','项目方案示意，','WinError 10013','EACCES'])
    assert all(p in appendix for p in ['不以5%绘柱','严格大于40.4个百分点','青海k=1、西藏k=2','不是互斥分层','h=(n−1)p'])
    assert md.count('$$')==10 and '{{EQ:' not in md
    figures=[];folder=ROOT/'docs/plan/ai-application/figures-sci'
    specs=json.loads((DATA/'figure-spec.json').read_text(encoding='utf-8'))['figures'];assert len(specs)==13
    for s in specs:
        p=folder/(s['id']+'.png')
        with Image.open(p) as im:
            assert min(im.info['dpi'])>=599 and im.mode=='P'
            size=im.size;dpi=im.info['dpi']
        svg=etree.parse(str(p.with_suffix('.svg')))
        texts=svg.xpath('//*[local-name()="text"]/text()')
        assert texts and not svg.xpath('//*[local-name()="image"]')
        assert not any(any(bad in t for bad in ['来源：','不作精确','不表示','不代表','项目方案示意']) for t in texts)
        assert not svg.xpath('//*[starts-with(@id,"figure_title") or starts-with(@id,"axes_title")]')
        assert p.with_suffix('.pdf').exists()
        figures.append({'id':s['id'],'sha256':sha(p),'svgSha256':sha(p.with_suffix('.svg')),'size':size,'dpi':dpi,'mode':'P','titleFreeChecked':True})
    rendered=json.loads(render.read_text(encoding='utf-8-sig'))
    assert Path(rendered['input']).resolve()==docx.resolve() and rendered['readOnly']
    html=ROOT/'deliverables/心域智链申报书正文审阅版.html'
    result={'status':'structural-checks-passed','updated':'2026-10-27','document':str(docx),'sha256':sha(docx),
      'htmlSha256':sha(html),'pages':rendered['pages'],'sections':3,'bodyTables':16,'bodyFigures':13,'nativeEquations':5,
      'references':27,'tableChecks':table_checks,'figures':figures,'educationRegions':31,'literatureRegions':31,
      'literatureOriginalRegions':33,'independentReview':{'status':'not-bound-by-this-invocation'}}
    if delivery:
        assert sha(delivery)==sha(docx);result.update(delivery=str(delivery.relative_to(ROOT)),deliverySha256=sha(delivery))
    if browser_report:
        checks=json.loads(browser_report.read_text(encoding='utf-8'));assert [c['width'] for c in checks]==[1440,390]
        for c in checks:
            assert c['tables']==16 and c['images']==c['svgImages']==13 and c['equations']==5
            assert not any(c[k] for k in ['imageFailures','overflow','errors','outside'])
            assert all(c[k] for k in ['centered','rules','navigation','appendixNavigation','notesInAppendix'])
        result['browserChecks']=checks
    if page_review:
        checks=json.loads(page_review.read_text(encoding='utf-8'));assert len(checks)==rendered['pages']
        for c in checks:
            assert c['reviewedBy']=='Lead' and c['result']=='pass'
            assert sha(page_review.parent/c['file'])==c['sha256']
        result['pageVisualReview']=checks
    if review_report:
        review=review_report.read_text(encoding='utf-8')
        mdpath=ROOT/'docs/plan/心域智链申报计划书.md'
        assert '**S5内容、结构与交付哈希独立复核通过。**' in review
        assert all(value in review for value in [sha(docx),sha(html),sha(mdpath)])
        result['independentReview']={'status':'passed','report':str(review_report.resolve().relative_to(ROOT)),
          'reportSha256':sha(review_report),'reviewedDocumentSha256':sha(docx),
          'reviewedHtmlSha256':sha(html),'reviewedMarkdownSha256':sha(mdpath),
          'scope':'Independent content/OOXML/data checks and selected rendered pages; full page/browser evidence by Lead.'}
        result['status']='review-copy-checks-passed'
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','pages','bodyTables','bodyFigures','nativeEquations']}))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--docx',required=True,type=Path)
    p.add_argument('--render',required=True,type=Path);p.add_argument('--report',required=True,type=Path);p.add_argument('--delivery',type=Path)
    p.add_argument('--browser-report',type=Path);p.add_argument('--page-review',type=Path)
    p.add_argument('--review-report',type=Path)
    a=p.parse_args();verify(a.docx.resolve(),a.render,a.report,a.delivery.resolve() if a.delivery else None,a.browser_report,a.page_review,a.review_report)
