"""Read-only verification of the regional-data revision and appendix placement."""
import argparse, hashlib, json, re  # noqa: E401, I001
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/plan/ai-application'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def txt(e):return ''.join(e.xpath('.//w:t/text()',namespaces=NS))

def verify(docx,render,report,delivery=None,browser_report=None,page_review=None):
    original=Path('C:/University/Files/附件.docx')
    assert sha(original)=='2531a2432493e4592d0759473fb3add5b6e1770e3c69ef1ee501d31b1943202a'
    with ZipFile(docx) as z,ZipFile(original) as old:
        tree=etree.fromstring(z.read('word/document.xml'))
        oldtree=etree.fromstring(old.read('word/document.xml'))
        tables=tree.findall('.//w:tbl',NS);assert len(tables)==15  # noqa: E702
        assert sum(txt(t).count('【待填写】') for t in tables[:3])==42
        for a,b in zip(tables[:3],oldtree.findall('.//w:tbl',NS)[:3]):  # noqa: B905
            for tag in ['tr','gridSpan','vMerge']:
                aa=a.findall('.//w:'+tag,NS);bb=b.findall('.//w:'+tag,NS)  # noqa: E702
                assert len(aa)==len(bb)
                if tag!='tr':assert [x.attrib for x in aa]==[x.attrib for x in bb]  # noqa: E701
        checks=[]
        for ti,t in enumerate(tables):
            rows=t.findall('w:tr',NS);header=2 if ti==0 else 0  # noqa: E702
            allowed={(0,'top'),(header,'bottom'),(len(rows)-1,'bottom')};rules=set()  # noqa: E702
            for border in t.findall('w:tblPr/w:tblBorders/*',NS):
                side=etree.QName(border).localname;value=border.get(W+'val')  # noqa: E702
                if value not in ('nil','none'):
                    assert side in ('top','bottom') and value=='single' and border.get(W+'sz')=='12'
                    rules.add((0 if side=='top' else len(rows)-1,side))
            for ri,row in enumerate(rows):
                for cell in row.findall('w:tc',NS):
                    assert cell.find('w:tcPr/w:vAlign',NS).get(W+'val')=='center'
                    for p in cell.findall('w:p',NS):assert p.find('w:pPr/w:jc',NS).get(W+'val')=='center'  # noqa: E701
                    for border in cell.findall('w:tcPr/w:tcBorders/*',NS):
                        side=etree.QName(border).localname;value=border.get(W+'val')  # noqa: E702
                        if value not in ('nil','none'):
                            assert (ri,side) in allowed and value=='single'
                            assert border.get(W+'sz')==('6' if (ri,side)==(header,'bottom') else '12')
                            rules.add((ri,side))
            assert rules==allowed,(ti,rules)
            if ti>=3:assert rows[0].find('w:trPr/w:tblHeader',NS) is not None  # noqa: E701
            checks.append({'table':ti+1,'rows':len(rows),'rules':3,'horizontal':'center','vertical':'center'})
        assert not tree.findall('.//w:trHeight[@w:hRule="exact"]',NS)
        paras=[txt(p) for p in tree.findall('.//w:body/w:p',NS)]
        for kind,total in [('图',10),('表',12)]:
            captions=[int(re.match(r'^'+kind+r'(\d+)\s',p)[1]) for p in paras if re.match(r'^'+kind+r'(\d+)\s',p)]
            assert captions==list(range(1,total+1)),(kind,captions)
        assert len(tree.findall('.//w:drawing',NS))==11
        assert len(tree.findall('.//w:sectPr',NS))==3
        refs=[p for p in paras if re.match(r'^\[\d+\]',p)]
        assert [int(re.match(r'^\[(\d+)\]',p)[1]) for p in refs]==list(range(1,25))
        md=(ROOT/'docs/plan/心域智链申报计划书.md').read_text(encoding='utf-8')
        main,appendix=md.split('## 附录A',1)
        for phrase in ['项目方案示意，依据当前代码核对与拟建设任务，不表示功能或效果已通过验收。',
          '数据来源：[4]。统计不覆盖港澳台。学校和学生规模是潜在服务场景的背景量，不是客户数、需求人数或收入测算基数。',
          'WinError 10013','EACCES','最近对话片段']:
            assert phrase not in main and phrase in appendix,phrase
        assert '数据来源：' not in main and '不表示功能或效果已通过验收' not in main
        assert '18.7%' not in md and '44.6%' not in md
        assert txt(tables[13]).count('【后期手动填写】')==7
        records=json.loads((BASE/'revision-20261027/regional-education-2024.json').read_text(encoding='utf-8'))['records']
        rows=tables[7].findall('w:tr',NS);assert len(rows)==32  # noqa: E702
        for row,record in zip(rows[1:],records):  # noqa: B905
            values=[txt(c) for c in row.findall('w:tc',NS)]
            expected=[record['region'],str(record['regular_vocational_heis'])]+[
              f'{record[key]/10000:.2f}' for key in ['normal_vocational_undergraduates','regular_senior_students','junior_students']]
            assert values==expected,(values,expected)
        services=tables[8].findall('w:tr',NS);assert len(services)==9  # noqa: E702
        assert '2026年报道' in txt(services[1]) and '要求每校至少1名' in txt(services[-1])
    manifest=json.loads((BASE/'visual-manifest.json').read_text(encoding='utf-8'))
    figures=[]
    for f in manifest['figures']:
        p=BASE/f['png']
        with Image.open(p) as im:
            assert min(im.info.get('dpi',[0,0]))>=299
            figures.append({'id':f['id'],'sha256':sha(p),'pixels':im.size,'dpi':im.info['dpi']})
        for source in f['sources']:assert source in manifest['sources']  # noqa: E701
    assert len([f for f in figures if (BASE/'figures'/f"{f['id']}.svg").exists()])==7
    rendered=json.loads(render.read_text(encoding='utf-8-sig'))
    assert Path(rendered['input']).resolve()==docx.resolve() and rendered['readOnly']
    html=ROOT/'deliverables/心域智链申报书正文审阅版.html'
    result={'updated':'2026-10-27','status':'revision-structural-checks-passed','document':str(docx),
      'sha256':sha(docx),'htmlSha256':sha(html),'pages':rendered['pages'],'sections':3,
      'retainedForms':3,'formPlaceholders':42,'bodyTables':12,'tableChecks':checks,'bodyFigures':10,
      'references':24,'regions':31,'serviceCases':8,'appendices':['A','B'],'figureAssets':figures,
      'scope':'Checks source preservation, native table formatting, data display and appendix placement. Visual and independent reviews recorded separately.'}
    if delivery:
        assert sha(delivery)==sha(docx)
        result['delivery']=str(delivery.relative_to(ROOT));result['deliverySha256']=sha(delivery)  # noqa: E702
    if browser_report:
        checks=json.loads(browser_report.read_text(encoding='utf-8'))
        assert [c['width'] for c in checks]==[1440,390]
        for c in checks:
            assert c['tables']==12 and c['images']==10 and c['headings']==10
            assert not any(c[k] for k in ['imageFailures','overflow','errors','outside'])
            assert all(c[k] for k in ['centered','rules','navigation','appendixNavigation','notesInAppendix'])
        result['browserChecks']=checks
    if page_review:
        checked=json.loads(page_review.read_text(encoding='utf-8'))
        assert len(checked)==rendered['pages']
        for page in checked:
            assert page['reviewedBy']=='Lead' and page['result']=='pass'
            assert sha(page_review.parent/page['file'])==page['sha256']
        result['pageVisualReview']=checked
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','pages','bodyTables','bodyFigures','references','regions']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docx',required=True,type=Path);p.add_argument('--render',required=True,type=Path)  # noqa: E702
    p.add_argument('--report',required=True,type=Path)
    p.add_argument('--delivery',type=Path);p.add_argument('--browser-report',type=Path);p.add_argument('--page-review',type=Path)  # noqa: E702
    a=p.parse_args()
    verify(a.docx.resolve(),a.render,a.report,a.delivery.resolve() if a.delivery else None,a.browser_report,a.page_review)
