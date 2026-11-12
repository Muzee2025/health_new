"""Read-only evidence for the enhanced application, distinct from the old 16-page verifier."""
import argparse, csv, hashlib, json, re  # noqa: E401, I001
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(docx,render,report,allow_pending):
    source=ROOT/'docs/plan/ai-application'
    manifest=json.loads((source/'visual-manifest.json').read_text(encoding='utf-8'))
    pending=not next(f for f in manifest['figures'] if f['id']=='fig05-mindmap').get('userStyleApproved')
    if pending and not allow_pending:raise AssertionError('User style review remains pending')  # noqa: E701
    original=Path('C:/University/Files/附件.docx')
    assert sha(original)=='2531a2432493e4592d0759473fb3add5b6e1770e3c69ef1ee501d31b1943202a'
    with ZipFile(docx) as z,ZipFile(original) as old:
        tree=etree.fromstring(z.read('word/document.xml'))
        oldtree=etree.fromstring(old.read('word/document.xml'))
        text=''.join(tree.xpath('//w:t/text()',namespaces=NS))
        tables=tree.findall('.//w:tbl',NS);assert len(tables)==12  # noqa: E702
        placeholders=text.count('【待填写】')
        form_placeholders=sum(''.join(t.xpath('.//w:t/text()',namespaces=NS)).count('【待填写】') for t in tables[:3])
        assert placeholders==43 and form_placeholders==42
        for i in range(3):
            a=tables[i];b=oldtree.findall('.//w:tbl',NS)[i]  # noqa: E702
            assert len(a.findall('w:tr',NS))==len(b.findall('w:tr',NS))
            assert [e.attrib for e in a.findall('.//w:gridSpan',NS)]==[e.attrib for e in b.findall('.//w:gridSpan',NS)]
            assert [e.attrib for e in a.findall('.//w:vMerge',NS)]==[e.attrib for e in b.findall('.//w:vMerge',NS)]
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
            checks.append({'table':ti+1,'rows':len(rows),'rules':3,'horizontal':'center','vertical':'center'})
        assert not tree.findall('.//w:trHeight[@w:hRule="exact"]',NS)
        paras=[''.join(p.xpath('.//w:t/text()',namespaces=NS)) for p in tree.findall('.//w:body/w:p',NS)]
        for kind,total in [('图',8),('表',9)]:
            captions=[int(re.match(r'^'+kind+r'(\d+)\s',p)[1]) for p in paras if re.match(r'^'+kind+r'(\d+)\s',p)]
            assert captions==list(range(1,total+1)),(kind,captions)
            references=''.join(p for p in paras if not p.startswith(kind))
            assert all(re.search(kind+str(n)+r'(?!\d)',references) for n in range(1,total+1))
        assert len(tree.findall('.//w:drawing',NS))==9  # Eight new figures plus retained school logo.
        assert len(tree.findall('.//w:sectPr',NS))==3
        assert all(s in text for s in ['135','WinError 10013','EACCES','最近对话片段'])
        assert '18.7%' not in text and '44.6%' not in text  # Unverified secondary-source additions excluded.
        assert '表3-2' not in text and '表3-3' not in text
        assert 'AI不作测评解释' not in text and '模型不用于测评解释' not in text
        assert '直接传送原文' in text and '不解释量表的临床意义' in text
        refs=[p for p in paras if re.match(r'^\[\d+\]',p)]
        assert len(refs)==11
    with (source/'chart-data.csv').open(encoding='utf-8-sig',newline='') as f:data=list(csv.DictReader(f))  # noqa: E701
    assert len(data)==len(manifest['metrics'])==21
    assert len([r for r in data if not r['value']])==1
    assert next(r for r in data if not r['value'])['reported']=='<5%'
    for row,metric in zip(data,manifest['metrics']):  # noqa: B905
        assert row['indicator']==metric['indicator'] and row['source']==metric['source']
        if row['value']:assert float(row['value'])==metric['value']  # noqa: E701
    figures=[]
    for f in manifest['figures']:
        p=source/f['png']
        with Image.open(p) as image:
            assert min(image.info.get('dpi',[0,0]))>=299
            figures.append({'id':f['id'],'sha256':sha(p),'pixels':image.size,'dpi':image.info['dpi']})
        for s in f['sources']:assert s in manifest['sources']  # noqa: E701
    rendered=json.loads(render.read_text(encoding='utf-8-sig'))
    assert Path(rendered['input']).resolve()==docx.resolve() and rendered['readOnly']
    result={'updated':'2026-10-27','status':'internal-checks-passed-style-pending' if pending else 'structural-checks-passed',
       'document':str(docx.relative_to(ROOT)),'sha256':sha(docx),'pages':rendered['pages'],'sections':3,
       'retainedForms':3,'bodyTables':9,'tables':checks,'bodyFigures':8,'registeredFigureAssets':figures,'sources':11,'metrics':21,
       'placeholderCount':placeholders,'formPlaceholderCount':form_placeholders,'userStyleReviewPending':pending,
       'scope':'Structural/data consistency only. Page images and independent review are separate evidence.'}
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','pages','retainedForms','bodyTables','metrics','placeholderCount']}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docx',required=True,type=Path);p.add_argument('--render',required=True,type=Path)  # noqa: E702
    p.add_argument('--report',required=True,type=Path);p.add_argument('--allow-pending-style',action='store_true')  # noqa: E702
    a=p.parse_args();verify(a.docx.resolve(),a.render,a.report,a.allow_pending_style)  # noqa: E702
