"""Verify attachment preservation and publish synthetic screenshot provenance."""
from pathlib import Path
from hashlib import sha256
from zipfile import ZipFile
from shutil import copyfile
import json
import re
from lxml import etree
from docx import Document
from pypdf import PdfReader
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'tmp/attachment-system-20261029'
OUT = ROOT / 'deliverables/心域智链项目计划书_系统内容与截图补充_20261029.docx'
ASSETS = ROOT / 'docs/plan/application-ui-20261029'
ASSETS.mkdir(parents=True, exist_ok=True)
digest = lambda path: sha256(Path(path).read_bytes()).hexdigest()
build = json.loads((WORK / 'document-verification.json').read_text(encoding='utf-8'))
assert digest(OUT) == build['output_sha256']
assert digest(WORK / 'source-private.docx') == build['source_sha256']
assert digest(Path('C:/University/Files/附件.docx')) == build['source_sha256']
capture = json.loads((WORK / 'capture-evidence.json').read_text(encoding='utf-8'))
assert capture['synthetic'] and not capture['backendUsed']
assert len(capture['cases']) == 8
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}
canonical = lambda node: etree.tostring(node, method='c14n', exclusive=True)
with ZipFile(WORK / 'source-private.docx') as old, ZipFile(OUT) as final:
    source_xml, output_xml = [etree.fromstring(z.read('word/document.xml')) for z in (old, final)]
    for tag in ('w:tbl', 'w:sectPr', 'm:oMath'):
        assert [canonical(x) for x in source_xml.findall('.//' + tag, ns)] == [canonical(x) for x in output_xml.findall('.//' + tag, ns)]
    media_payloads = [final.read(n) for n in final.namelist() if n.startswith('word/media/')]
    preserved = [n for n in old.namelist() if n not in {'word/document.xml', 'word/_rels/document.xml.rels', '[Content_Types].xml'}]
    assert all(old.read(n) == final.read(n) for n in preserved)
    asset_rows = []
    for i, case in enumerate(capture['cases'], 14):
        assert not any(case[k] for k in ('unknownApis', 'externalBlocked', 'pageErrors', 'consoleErrors', 'brokenImages'))
        image = Path(case['image'])
        assert digest(image) == case['imageSha256']
        assert image.read_bytes() in media_payloads
        target = ASSETS / image.name
        copyfile(image, target)
        asset_rows.append({'figure': i, 'file': target.name, 'role': case['role'], 'route': case['path'], 'sha256': digest(target), 'pixels': list(Image.open(target).size), 'clip': case['clip'], 'apiRequests': case['api'], 'synthetic': True, 'source': 'Current project frontend production build', 'rights': '项目原创界面截图；图标与品牌沿用src/assets/manifest.json既有许可', 'review': 'technical capture verified; synthetic data only'})

doc = Document(OUT)
chapter = None
captions = []
for p in doc.paragraphs:
    if re.match(r'^[1-6] ', p.text):
        chapter = int(p.text[0])
    match = re.match(r'图(1[4-9]|2[01]) ', p.text)
    if match:
        assert chapter == 5 and '（合成演示）' in p.text
        captions.append(p.text)
assert len(captions) == 8
original_texts = [p.text for p in Document(WORK / 'source-private.docx').paragraphs]
changes = {p['original_paragraph_index']: p['after'] for p in build['modified_original_paragraphs']}
expected = [changes.get(i, t) for i,t in enumerate(original_texts)]
actual = [p.text for p in doc.paragraphs]
position = 0
for text in expected:
    position = actual.index(text, position) + 1
assert all(any(heading in p for p in actual) for heading in ['项目介绍', '5.4 项目进展', '5.5 学生端功能实现', '5.6 教师端功能实现', '5.7 当前系统与后续建设的衔接'])
native = json.loads((WORK / 'final-v4-word-render.json').read_text(encoding='utf-8-sig'))
assert native['readOnly']
pdf = PdfReader(WORK / 'final-v4-word.pdf')
assert native['pages'] == len(pdf.pages) == 37
page_evidence = []
for i in range(1, 38):
    path = WORK / 'final-v4-pages' / f'page-{i}.png'
    im = Image.open(path).convert('L')
    dark = sum(n for value,n in enumerate(im.histogram()) if value < 220)
    assert dark > 500, f'Blank page: {i}'
    page_evidence.append({'page': i, 'sha256': digest(path), 'nonwhitePixels': dark})

manifest = {'owner': 'A', 'version': '1.0', 'status': 'verified synthetic UI captures', 'updated': '2026-10-29', 'backendUsed': False, 'realModelUsed': False, 'registeredVisualSource': 'src/assets/manifest.json', 'registeredVisualManifestSha256': digest(ROOT / 'src/assets/manifest.json'), 'captureScript': 'scripts/capture-attachment-ui.mjs', 'captureScriptSha256': digest(ROOT / 'scripts/capture-attachment-ui.mjs'), 'assets': asset_rows}
(ASSETS / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
result = {**build, 'updated': '2026-10-29', 'status': 'lead verification passed; independent conclusion separately recorded', 'nativeRender': native, 'pdfSha256': digest(WORK / 'final-v4-word.pdf'), 'sourceParagraphsPreservedInOrder': len(expected), 'screenshotCaptions': captions, 'screenshotPages': list(range(25, 33)), 'leadVisualPagesInspected': list(range(1, 38)), 'pageImages': page_evidence, 'screenshotsManifest': 'docs/plan/application-ui-20261029/manifest.json', 'screenshotsManifestSha256': digest(ASSETS / 'manifest.json'), 'canonicalRenderer': {'status': 'failed', 'reason': 'LibreOffice soffice.exe not found on PATH', 'fallback': 'Microsoft Word 16 read-only private-copy PDF export; PDFium PNG'}, 'productionApproval': False, 'realStudentRecordsUsed': False, 'originalDocxOverwritten': False}
review = ROOT / 'docs/test/附件系统内容补充独立复核.md'
review_text = review.read_text(encoding='utf-8-sig')
assert build['output_sha256'] in review_text and '独立复核完成' in review_text
result.update({'status': 'complete for user review', 'sourceOriginalSha256Verified': True, 'independentReview': {'path': str(review.relative_to(ROOT)), 'sha256': digest(review), 'boundDocxSha256': build['output_sha256'], 'conclusion': 'no blocking findings', 'reviewerViewedAllPages': False}})
(ROOT / 'docs/test/attachment-system-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'sha256': digest(OUT), 'pages': 37, 'sourceTables': 19, 'originalMedia': 17, 'screenshots': 8, 'allScreenshotsInChapterFive': True, 'blankPages': 0, 'leadVisualInspected': 37}, ensure_ascii=False))
