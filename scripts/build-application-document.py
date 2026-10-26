"""Fill the retained application template with package-local XML edits.

The supplied template and every non-document ZIP part remain unchanged.
Use the bundled workspace Python. Draft output paths must be new.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
XML = '{http://www.w3.org/XML/1998/namespace}'


def element(name, **values):
    result = etree.Element(W + name)
    for key, value in values.items():
        result.set(W + key, str(value))
    return result


def clean(text):
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'{m[1]}（{m[2]}）', text)
    return text.replace('**', '').replace('`', '')


def run(text, size=24, bold=False):
    r = element('r')
    props = element('rPr')
    props.append(element('rFonts', ascii='宋体', hAnsi='宋体', eastAsia='宋体'))
    props.extend([element('sz', val=size), element('szCs', val=size), element('color', val='000000')])
    if bold:
        props.append(element('b'))
    r.append(props)
    pieces = clean(text).split('\n')
    for index, value in enumerate(pieces):
        if index:
            r.append(element('br'))
        t = element('t')
        t.set(XML + 'space', 'preserve')
        t.text = value
        r.append(t)
    return r


def set_paragraph_text(p, text, size=24, bold=False):
    for child in list(p):
        if child.tag != W + 'pPr':
            p.remove(child)
    p.append(run(text, size=size, bold=bold))


def fill_cell(cell, text):
    paragraphs = cell.findall('w:p', NS)
    p = paragraphs[0] if paragraphs else element('p')
    if not paragraphs:
        cell.append(p)
    set_paragraph_text(p, text)
    for extra in paragraphs[1:]:
        cell.remove(extra)


def paragraph(text, prototype, *, heading=False, table=False, reference=False):
    p = deepcopy(prototype)
    props = p.find('w:pPr', NS)
    if props is None:
        props = element('pPr')
        p.insert(0, props)
    for name in ('sectPr', 'pageBreakBefore', 'outlineLvl', 'spacing', 'ind', 'jc', 'keepNext', 'keepLines', 'snapToGrid'):
        for old in props.findall('w:' + name, NS):
            props.remove(old)
    props.append(element('jc', val='left' if heading or table or reference else 'both'))
    props.append(element('snapToGrid', val='0'))
    if heading:
        props.extend([element('keepNext'), element('keepLines'), element('spacing', before=180, after=100, line=300, lineRule='auto')])
    else:
        props.append(element('spacing', before=0, after=60 if table else 90, line=280 if table else 320, lineRule='auto'))
        if not table and not reference:
            props.append(element('ind', firstLine=480))
    set_paragraph_text(p, text, size=21 if reference else 22 if table else 24, bold=heading)
    if reference and text.startswith('https://'):
        fonts = p.find('w:r/w:rPr/w:rFonts', NS)
        fonts.set(W + 'ascii', 'Arial')
        fonts.set(W + 'hAnsi', 'Arial')
        for font_size in p.findall('w:r/w:rPr/w:sz', NS) + p.findall('w:r/w:rPr/w:szCs', NS):
            font_size.set(W + 'val', '18')
    return p


def body_table(rows, prototype, paragraph_prototype):
    table = element('tbl')
    props = deepcopy(prototype.find('w:tblPr', NS))
    for old in props.findall('w:tblW', NS) + props.findall('w:tblInd', NS) + props.findall('w:tblLayout', NS):
        props.remove(old)
    props.extend([element('tblW', w=8306, type='dxa'), element('tblLayout', type='fixed')])
    table.append(props)
    count = len(rows[0])
    fractions = [0.24, 0.38, 0.38] if count == 3 else [1 / count] * count
    widths = [round(8306 * fraction) for fraction in fractions]
    widths[-1] = 8306 - sum(widths[:-1])
    grid = element('tblGrid')
    grid.extend(element('gridCol', w=width) for width in widths)
    table.append(grid)
    for index, values in enumerate(rows):
        row = element('tr')
        row_props = element('trPr')
        row_props.append(element('cantSplit'))
        if index == 0:
            row_props.append(element('tblHeader'))
        row.append(row_props)
        for column, text in enumerate(values):
            cell = element('tc')
            cp = element('tcPr')
            cp.append(element('tcW', w=widths[column], type='dxa'))
            cell.append(cp)
            p = paragraph(text, paragraph_prototype, table=True)
            if index == 0:
                p.find('w:r/w:rPr', NS).append(element('b'))
                p.find('w:pPr', NS).append(element('keepNext'))
            cell.append(p)
            row.append(cell)
        table.append(row)
    return table


def three_line_table(table, header_row=0):
    """Use only top, header separator and bottom rules, including source forms."""
    props = table.find('w:tblPr', NS)
    for name in ('tblBorders', 'tblStyle', 'tblLook', 'tblCellSpacing'):
        for old in props.findall('w:' + name, NS):
            props.remove(old)
    borders = element('tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        borders.append(element(side, val='nil'))
    props.append(borders)
    # Direct cell borders avoid inherited table-style and merged-cell grid rules.
    for old in table.findall('.//w:tcBorders', NS) + table.findall('.//w:pBdr', NS) + table.findall('.//w:tblPrEx/w:tblBorders', NS):
        old.getparent().remove(old)
    rows = table.findall('w:tr', NS)
    for ri, row in enumerate(rows):
        for cell in row.findall('w:tc', NS):
            cp = cell.find('w:tcPr', NS)
            if cp is None:
                cp = element('tcPr')
                cell.insert(0, cp)
            borders = element('tcBorders')
            for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
                rule = (side == 'top' and ri == 0) or (side == 'bottom' and ri in (header_row, len(rows) - 1))
                if rule:
                    borders.append(element(side, val='single', sz=12 if ri == len(rows)-1 or side == 'top' else 6,
                                           space=0, color='000000'))
                else:
                    borders.append(element(side, val='nil'))
            cp.append(borders)


def build(reference, plan_path, content_path, output):
    if output.exists():
        raise ValueError('Use a new draft output path')
    before_hash = hashlib.sha256(reference.read_bytes()).hexdigest()
    content = json.loads(content_path.read_text(encoding='utf-8-sig'))
    summary = content.get('summary') or content.get('projectSummary')
    if not isinstance(summary, str) or not 100 <= len(summary) <= 300:
        raise ValueError('Expected a 100-300 character summary')
    with ZipFile(reference) as source:
        original = source.read('word/document.xml')
        tree = etree.fromstring(original)
        body = tree.find('w:body', NS)
        original_children = list(body)
        tables = body.findall('w:tbl', NS)
        if len(tables) != 3:
            raise ValueError('Template table contract changed')
        def cell(t, r, c):
            return tables[t].findall('w:tr', NS)[r].findall('w:tc', NS)[c]
        fill_cell(cell(0, 0, 1), '心域智链校园心理支持协作平台')
        for row in range(3, 8):
            for value in tables[0].findall('w:tr', NS)[row].findall('w:tc', NS)[1:]:
                fill_cell(value, '【待填写】')
        for row in (9, 10):
            for value in tables[0].findall('w:tr', NS)[row].findall('w:tc', NS)[1:]:
                fill_cell(value, '【待填写】')
        fill_cell(cell(0, 12, 1), summary)
        fill_cell(cell(1, 0, 1), '心域智链校园心理支持协作平台')
        fill_cell(cell(1, 1, 1), '【待填写】元')
        fill_cell(cell(1, 2, 1), '【待填写】')
        fill_cell(cell(1, 2, 3), '【待填写】')
        fill_cell(cell(1, 4, 0), summary)
        for row in range(7):
            fill_cell(cell(2, row, 2), '心域智链校园心理支持协作平台' if row == 0 else '【待填写】')
        for text in original_children[14].iter(W + 't'):
            if text.text:
                text.text = text.text.replace('（模板）', '')
        # Only source instruction blocks after the plan-title slot are replaced.
        paragraph_prototype = original_children[32]
        heading_prototype = original_children[30]
        for child in list(body)[19:]:
            if child.tag != W + 'sectPr':
                body.remove(child)
        final_section = body.find('w:sectPr', NS)
        lines = plan_path.read_text(encoding='utf-8-sig').splitlines()
        start = next(i for i, line in enumerate(lines) if re.match(r'## 一[、 ]', line))
        index = start
        in_references = False
        while index < len(lines):
            line = lines[index].strip()
            if not line or line.startswith('>'):
                index += 1
                continue
            if line.startswith('```'):
                index += 1
                while index < len(lines) and not lines[index].startswith('```'):
                    index += 1
                index += 1
                rows = [
                    ['系统层级', '职责与数据边界'],
                    ['学生与教师工作区', '学生测评与支持入口；教师仅访问明确分配的学生和授权事项。'],
                    ['FastAPI授权接口', '身份、角色和资源校验，记录求助、审核、跟进与单生导出。'],
                    ['本机SQLite副本', '当前工程验证存储；正式数据、生产数据库和校级身份接入另行审批验收。'],
                    ['隔离评测工具', '只处理合成案例、人工评分和失败记录；真实模型接入前须完成审批与专业审查。'],
                ]
                body.insert(body.index(final_section), body_table(rows, tables[0], paragraph_prototype))
                continue
            if line.startswith('|'):
                rows = []
                while index < len(lines) and lines[index].strip().startswith('|'):
                    values = [value.strip() for value in lines[index].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-{3,}:?', value) for value in values):
                        rows.append(values)
                    index += 1
                block = body_table(rows, tables[0], paragraph_prototype)
            else:
                is_heading = line.startswith('#')
                text = line.lstrip('#').strip()
                if is_heading and ('参考' in text or '来源' in text):
                    in_references = True
                if not is_heading:
                    text = re.sub(r'^[-*] ', '', text)
                block = paragraph(text, heading_prototype if is_heading else paragraph_prototype,
                                  heading=is_heading, reference=in_references and not is_heading)
                index += 1
            body.insert(body.index(final_section), block)
        # User's 2026-10-27 format update explicitly includes every table,
        # including the application/introduction forms and the cover layout.
        for ti, table in enumerate(body.findall('w:tbl', NS)):
            three_line_table(table, header_row=2 if ti == 0 else 0)
        data = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, 'x') as final:
            for info in source.infolist():
                final.writestr(info, data if info.filename == 'word/document.xml' else source.read(info.filename))
    with ZipFile(reference) as old, ZipFile(output) as new:
        preserved = [name for name in old.namelist() if name != 'word/document.xml']
        assert set(old.namelist()) == set(new.namelist())
        assert all(old.read(name) == new.read(name) for name in preserved)
        a = etree.fromstring(old.read('word/document.xml'))
        b = etree.fromstring(new.read('word/document.xml'))
        assert [etree.tostring(x) for x in a.findall('.//w:sectPr', NS)] == [etree.tostring(x) for x in b.findall('.//w:sectPr', NS)]
    assert before_hash == hashlib.sha256(reference.read_bytes()).hexdigest()
    print(json.dumps({'output': str(output), 'summaryCharacters': len(summary), 'preserveOnlyParts': len(preserved),
                      'referenceUnchanged': True, 'sections': 3, 'sourceSha256': before_hash}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=Path('C:/University/Files/附件.docx'))
    parser.add_argument('--plan', type=Path, default=ROOT / 'docs/plan/心域智链申报计划书.md')
    parser.add_argument('--content', type=Path, default=ROOT / 'docs/plan/申报表字段.json')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    build(args.reference, args.plan, args.content, args.output)
