"""Verify the complete revised plan and its source/visual preservation."""
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
import json
import re
from lxml import etree
from pypdf import PdfReader
from PIL import Image
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/project-plan-revision-20261029'
build = json.loads((WORK / 'build-verification.json').read_text(encoding='utf-8'))
base, output = Path(build['base']), Path(build['output'])
digest = lambda p: sha256(Path(p).read_bytes()).hexdigest()
assert digest(base) == build['baseSha256'] == 'b57452d9cf98353e58c862778a7f4ba9fe7b804317db481c6ad000fe63e3641e'
assert digest(output) == build['sha256']
assert digest('C:/University/Files/附件.docx') == 'f2dc7a1b9fe60be8cdc37dd02f98c5856aa27bf7d780cb44b87a79b8126cc2ec'
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math', 'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
canonical = lambda e: etree.tostring(e, method='c14n', exclusive=True)
with ZipFile(base) as old, ZipFile(output) as final:
    a, b = [etree.fromstring(z.read('word/document.xml')) for z in (old, final)]
    old_tables, new_tables = [x.findall('.//w:tbl', ns) for x in (a, b)]
    assert len(old_tables) == 19 and len(new_tables) == 20
    for i, table in enumerate(old_tables):
        if i != 6:
            assert canonical(table) == canonical(new_tables[i if i < 17 else i+1])
    for tag in ('w:sectPr', 'm:oMath'):
        assert [canonical(e) for e in a.findall('.//' + tag, ns)] == [canonical(e) for e in b.findall('.//' + tag, ns)]
    for name in old.namelist():
        if name not in {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}:
            assert old.read(name) == final.read(name)
    media = [n for n in old.namelist() if n.startswith('word/media/')]
    assert len(media) == 25 and all(old.read(n) == final.read(n) for n in media)
    rels = etree.fromstring(final.read('word/_rels/document.xml.rels'))
    hyperlinks = {r.get('Target') for r in rels if r.get('Type', '').endswith('/hyperlink')}
    assert {r['url'] for r in build['referencesRestored']} <= hyperlinks
    new_table = new_tables[17]
    assert all(e.get('{'+ns['w']+'}val') == 'center' for e in new_table.findall('.//w:jc', ns))
    assert len(new_table.findall('.//w:tcPr/w:vAlign', ns)) == 18
    assert all(e.get('{'+ns['w']+'}val') == 'center' for e in new_table.findall('.//w:vAlign', ns))
    borders = new_table.find('./w:tblPr/w:tblBorders', ns)
    assert [borders.find('w:'+name, ns).get('{'+ns['w']+'}val') for name in ('top','bottom','insideH','insideV')] == ['single','single','nil','nil']

doc = Document(output)
texts = [p.text for p in doc.paragraphs]
for heading in ('项目介绍', '5.4 项目进展', '6.3 预期成果与检查方法', '6.4 阶段安排与交付', '附录A 系统截图与实现范围说明', '附录B 资料口径与参考来源'):
    assert heading in texts, heading
references = [int(m.group(1)) for t in texts if (m := re.match(r'^\[(\d+)\] ', t))]
assert references == list(range(1, 27))
assert doc.tables[6].rows[-1].cells[0].text == '学校（规划）'
assert [c.text for c in doc.tables[16].rows[-1].cells][-1] == '5000元' or '5000' in doc.tables[16].rows[-1].cells[-1].text
chapter = None
captions = []
for text in texts:
    if re.match(r'^[1-6] ', text):
        chapter = int(text[0])
    if re.match(r'^图(1[4-9]|2[01]) ', text):
        assert chapter == 5 and '合成演示' in text
        captions.append(text)
assert len(captions) == 8

native = json.loads((WORK / 'word-v2-render.json').read_text(encoding='utf-8-sig'))
assert native['readOnly'] and native['pages'] == 40 and native['sections'] == 3
assert digest(native['input']) == digest(output)
pdf = PdfReader(WORK / 'word-v2.pdf')
assert len(pdf.pages) == 40
pdf_urls = {str(a.get_object().get('/A', {}).get('/URI', '')) for page in pdf.pages for a in page.get('/Annots', [])}
assert {r['url'] for r in build['referencesRestored']} <= pdf_urls
assert '6.3' in (pdf.pages[33].extract_text() or '') and '6.4' in (pdf.pages[33].extract_text() or '')
assert all('图'+str(n) in re.sub(r'\s+', '', pdf.pages[n+10].extract_text() or '') for n in range(14, 22))

prior_visual = json.loads((ROOT / 'docs/test/attachment-system-verification.json').read_text(encoding='utf-8'))
prior_hashes = {x['sha256']: x['page'] for x in prior_visual['pageImages']}
current_viewed = {12, 20, 24, 33, 34, 35, 36, 37}
page_evidence = []
for i in range(1, 41):
    path = WORK / 'pages-v2' / f'page-{i}.png'
    h = digest(path)
    prior_page = prior_hashes.get(h)
    assert i in current_viewed or prior_page in prior_visual['leadVisualPagesInspected']
    im = Image.open(path).convert('L')
    assert sum(n for v,n in enumerate(im.histogram()) if v < 220) > 500
    page_evidence.append({'page': i, 'sha256': h, 'currentVisualInspection': i in current_viewed, 'identicalPreviouslyInspectedPage': prior_page})
review = ROOT / 'docs/test/策划书内容完善独立复核.md'
review_text = review.read_text(encoding='utf-8-sig')
assert build['sha256'] in review_text

result = {**build, 'status': 'complete for user review', 'scopeClarification': '用户最新明确本对话任务为修改策划书；PPT不作为本轮完成条件', 'sourceAttachmentUnchanged': True, 'base37PageDeliverableUnchanged': True, 'nativeRender': native, 'nativePdfSha256': digest(WORK / 'word-v2.pdf'), 'allSourceLinksInDocxAndPdf': 26, 'screenshotPages': list(range(25,33)), 'newTableAndStagesPage': 34, 'sourcePages': [36,37], 'supportingEvidencePages': [38,39,40], 'visualPages': page_evidence, 'currentPagesVisuallyInspected': sorted(current_viewed), 'pixelIdenticalReusedPages': sum(x['identicalPreviouslyInspectedPage'] is not None and not x['currentVisualInspection'] for x in page_evidence), 'all40PagesCoveredByVisualEvidence': True, 'independentReview': {'path': str(review.relative_to(ROOT)), 'sha256': digest(review), 'boundDocxSha256': build['sha256'], 'scope': 'structure, wording and source registration; no full-page visual review'}, 'canonicalRenderer': 'failed: soffice.exe unavailable; used Microsoft Word 16 read-only private-copy export and PDFium', 'businessCodeModified': False, 'businessDatabaseUsed': False, 'realModelUsed': False, 'productionApproval': False}
(ROOT / 'docs/test/project-plan-revision-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'status': result['status'], 'sha256': build['sha256'], 'pages': 40, 'tables': 20, 'sourceLinks': 26, 'screenshotsInChapter5': 8, 'visualNewPages': len(current_viewed), 'pixelIdenticalReusedPages': result['pixelIdenticalReusedPages']}, ensure_ascii=False))
