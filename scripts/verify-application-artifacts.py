"""Read-only application/outline checks including all three-line table rules."""
import argparse  # noqa: I001
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
REFERENCE_HASH='2531a2432493e4592d0759473fb3add5b6e1770e3c69ef1ee501d31b1943202a'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def inspect_table(table,number):
    rows=table.findall('w:tr',NS)
    header=2 if number==1 else 0
    assert not table.findall('.//w:pBdr',NS)
    for border in table.findall('w:tblPr/w:tblBorders/*',NS):
        assert border.get(W+'val')=='nil'
    rule_positions=set()
    for ri,row in enumerate(rows):
        for cell in row.findall('w:tc',NS):
            borders=cell.find('w:tcPr/w:tcBorders',NS)
            assert borders is not None
            for b in borders:
                side=etree.QName(b).localname
                expected=(side=='top' and ri==0) or (side=='bottom' and ri in (header,len(rows)-1))
                assert b.get(W+'val')==('single' if expected else 'nil')
                if expected:
                    assert b.get(W+'sz')==('12' if side=='top' or ri==len(rows)-1 else '6')
                    rule_positions.add((ri,side))
    assert len(rule_positions)==3
    return {'table':number,'rows':len(rows),'headerLastRow':header,'horizontalRules':3,'verticalRules':0}


def verify(docx,outline,template,qa):
    assert sha(template)==REFERENCE_HASH
    summary=json.loads((ROOT/'docs/plan/申报表字段.json').read_text(encoding='utf-8'))['summary']
    with ZipFile(template) as old,ZipFile(docx) as new:
        assert set(old.namelist())==set(new.namelist())
        preserved=[p for p in old.namelist() if p!='word/document.xml']
        assert all(old.read(p)==new.read(p) for p in preserved)
        a=etree.fromstring(old.read('word/document.xml'));b=etree.fromstring(new.read('word/document.xml'))  # noqa: E702
        assert [etree.tostring(x) for x in a.findall('.//w:sectPr',NS)]==[etree.tostring(x) for x in b.findall('.//w:sectPr',NS)]
        text=''.join(b.xpath('//w:t/text()',namespaces=NS))
        assert text.count(summary)==2 and len(summary)==218
        assert text.count('【待填写】')==42
        assert all(s in text for s in ['一、实用性与创新力','二、产品与服务','三、市场分析','四、营销策略','五、方案实现','六、项目预算','40.7','24.6','65.3','96.5','EACCES'])
        with ZipFile(qa/'application-v2.docx') as previous:
            prev=etree.fromstring(previous.read('word/document.xml'))
            assert prev.xpath('//w:t/text()',namespaces=NS)==b.xpath('//w:t/text()',namespaces=NS),'Formatting changed content'
        tables=b.findall('.//w:tbl',NS)
        rules=[inspect_table(t,i) for i,t in enumerate(tables,1)]
        assert len(rules)==8
    with ZipFile(outline) as z:
        tree=etree.fromstring(z.read('word/document.xml'))
        assert not tree.findall('.//w:tbl',NS)
        headings=tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="Heading2"]]',namespaces=NS)
        assert len(headings)==16
        outline_text=''.join(tree.xpath('//w:t/text()',namespaces=NS))
        assert '供后续自行制作PPT' in outline_text
        assert all(s in outline_text for s in ['40.7','24.6','65.3','96.5','135','EACCES','【待填写】'])
        assert not tree.findall('.//w:pBdr',NS)
        styles=etree.fromstring(z.read('word/styles.xml'))
        assert not styles.findall('.//w:pBdr',NS)
    document={'path':docx.relative_to(ROOT).as_posix(),'sha256':sha(docx),'pages':16,'sections':3,
              'preservedParts':17,'summaryCharacters':218,'editablePlaceholders':42,'threeLineTables':rules}
    outline_info={'path':outline.relative_to(ROOT).as_posix(),'sha256':sha(outline),'pages':4,'topics':16,'tables':0}
    for filename,pages in [('application-three-line-v1-render.json',16),('outline-v2-render.json',4)]:
        r=json.loads((qa/filename).read_text(encoding='utf-8-sig'))
        assert r['pages']==pages and r['readOnly']
    assert sha(qa/'application-three-line-v1.docx')==document['sha256']
    assert sha(qa/'outline-v2.docx')==outline_info['sha256']
    visual=json.loads((qa/'three-line-visual-review.json').read_text(encoding='utf-8'))
    assert visual['documentSha256']==document['sha256'] and visual['outlineSha256']==outline_info['sha256']
    assert visual['documentPages']==list(range(1,17)) and visual['outlinePages']==[1,2,3,4] and visual['result']=='pass'
    return {'status':'pass','updated':'2026-10-27','request':'Application with every table in three-line format; PPT outline only',
            'referenceSha256':REFERENCE_HASH,'document':document,'outline':outline_info,'visualReview':visual,
            'scope':'Documents only; no PPTX delivery, business integration or school/professional approval inferred.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docx',type=Path,default=ROOT/'deliverables/心域智链项目申报材料.docx')
    p.add_argument('--outline',type=Path,default=ROOT/'deliverables/心域智链项目答辩大纲.docx')
    p.add_argument('--template',type=Path,default=Path('C:/University/Files/附件.docx'))
    p.add_argument('--qa',type=Path,default=ROOT/'tmp/application-delivery-20261026')
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();report=verify(a.docx.resolve(),a.outline.resolve(),a.template,a.qa.resolve())  # noqa: E702
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
