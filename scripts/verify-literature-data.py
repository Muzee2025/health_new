"""Independently check aggregate extraction, formula caches and data package contents."""
import hashlib
import importlib.util
import json
import math
import re
import statistics
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/plan/research-data-20261028'
WORK=ROOT/'tmp/literature-data-20261028'
BOOK=ROOT/'deliverables/心域智链_文献数据下载与分析_20261028.xlsx'
PACK=ROOT/'deliverables/心域智链_公开文献数据包_20261028.zip'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data=json.loads((PUBLIC/'processed-data.json').read_text(encoding='utf-8'));d=data['datasets']
    assert len(d['sources'])==6 and all(r['authors'] for r in d['sources'])
    assert len(d['publication_year_groups'])==31 and sum(r['studies_k'] for r in d['publication_year_groups'])==439
    assert sum(r['sample_n'] for r in d['publication_year_groups'])==1497524
    assert len(d['ai_trial_characteristics'])==15 and sum(r['reported_n'] for r in d['ai_trial_characteristics'])==1901
    assert len(d['adjusted_associations'])==73
    assert len({(r['source_id'],r['population'],r['outcome'],r['factor'],r['comparison']) for r in d['adjusted_associations']})==73
    assert all(r['ci95_lower']<=r['estimate']<=r['ci95_upper'] for r in d['screening_aggregates'])
    assert all(r['ci95_lower']<=r['adjusted_or']<=r['ci95_upper'] for r in d['adjusted_associations'])
    sleep=next(r for r in d['adjusted_associations'] if r['source_id']=='CHEN2023' and r['population']=='全部中学生' and r['factor']=='Sleep Disturbance')
    assert (sleep['adjusted_or'],sleep['ci95_lower'],sleep['ci95_upper'])==(6.99,6.69,7.30)
    spec=importlib.util.spec_from_file_location('research_processor',ROOT/'scripts/process-literature-data.py')
    processor=importlib.util.module_from_spec(spec);spec.loader.exec_module(processor)
    headers,participants=processor.read_xlsx(WORK/'raw/YANG2023-12888_2023_4972_MOESM1_ESM.xlsx')
    assert len(participants)==926 and len(headers)==74
    for r in d['microdata_dictionary']:
        present=sum(x.get(r['variable']) not in (None,'') for x in participants)
        assert present==r['nonmissing_n'] and 926-present==r['missing_n']
    bdi=[float(x['BDI_II_Total']) for x in participants if isinstance(x.get('BDI_II_Total'),(int,float))]
    assert len(bdi)==918
    mean=next(x['value'] for x in d['microdata_quality'] if x['metric']=='访谈样本BDI-II均值')
    assert math.isclose(statistics.mean(bdi),mean,abs_tol=1e-12)
    weights=[float(x['weight']) for x in participants]
    kish=sum(weights)**2/sum(x*x for x in weights)
    assert math.isclose(kish,next(x['value'] for x in d['microdata_quality'] if x['metric']=='weight有效样本量近似'),abs_tol=1e-10)
    for r in d['downloaded_files']:assert sha(WORK/r['local_relative_path'])==r['sha256']
    with zipfile.ZipFile(BOOK) as z:
        strings=[''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
        def cv(c):
            if c.get('t')=='inlineStr':return ''.join(c.find('m:is',NS).itertext())
            v=c.find('m:v',NS)
            if v is None:return None
            if c.get('t')=='s':return strings[int(v.text)]
            assert c.get('t')!='e','XLSX error cell'
            if v.text is None:return None
            try:return float(v.text)
            except ValueError:return v.text
        paths=sorted([n for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml',n)],key=lambda n:int(re.search(r'sheet(\d+)',n).group(1)))
        trees=[ET.fromstring(z.read(n)) for n in paths]
        sheets=[{c.get('r'):cv(c) for c in t.findall('.//m:sheetData/m:row/m:c',NS)} for t in trees]
        assert len(sheets)==12
        assert sheets[0]['B7']==6 and sheets[0]['B8']==26 and sheets[0]['B9']==926 and sheets[0]['B10']==74
        assert math.isclose(sheets[0]['B11'],20.4,abs_tol=1e-12) and math.isclose(sheets[0]['B12'],17.7,abs_tol=1e-12) and sheets[0]['B13']==8
        assert sheets[9]['D24']==1901
        for row,r in enumerate(d['microdata_dictionary'],7):
            assert sheets[6][f'B{row}']==r['variable'] and sheets[6][f'G{row}']==r['missing_n']
            assert math.isclose(sheets[6][f'H{row}'],r['missing_rate'],abs_tol=1e-12)
        for row,r in enumerate(d['survey_waves'],7):
            assert sheets[2][f'E{row}']==r['sample_n'] and sheets[2][f'I{row}']==r['estimate']
        for row,r in enumerate(d['adjusted_associations'],7):
            assert sheets[5][f'E{row}']==r['factor'] and sheets[5][f'G{row}']==r['reference'] and sheets[5][f'H{row}']==r['adjusted_or']
        for row,r in enumerate(d['ai_effects'],7):
            assert sheets[8][f'E{row}']==r['hedges_g'] and sheets[8][f'F{row}']==r['ci95_lower'] and sheets[8][f'G{row}']==r['ci95_upper']
            expected='CI不跨0' if r['ci_excludes_zero'] else 'CI跨0'
            assert sheets[8][f'J{row}']==expected
        formula_count=0
        for t in trees:
            for c in t.findall('.//m:c',NS):
                if c.find('m:f',NS) is not None:
                    formula_count+=1
                    assert c.find('m:v',NS) is not None,'Formula cache missing'
        table_paths=[n for n in z.namelist() if re.fullmatch(r'xl/tables/table\d+\.xml',n)]
        assert len(table_paths)==14
        for n in table_paths:assert ET.fromstring(z.read(n)).find('m:autoFilter',NS) is not None
        chart_paths=[n for n in z.namelist() if re.fullmatch(r'xl/(?:drawings/)?charts/chart\d+\.xml',n)]
        assert len(chart_paths)==1
        chart=ET.fromstring(z.read(chart_paths[0]));assert len(chart.findall('.//c:ser',NS))==2
        xml=z.read(chart_paths[0]).decode('utf-8');assert '604372' in xml and '8BA696' in xml
    with zipfile.ZipFile(PACK) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if n.startswith('raw_public/')])==25
        assert not any(n.lower().endswith(('.xlsx','.db','.sqlite','.sqlite3','.env')) for n in z.namelist())
        for r in d['downloaded_files']:
            name='raw_public/'+r['file']
            if r['file'].endswith('.xlsx'):assert name not in z.namelist()
            else:assert hashlib.sha256(z.read(name)).hexdigest()==r['sha256']
        for f in PUBLIC.glob('*.csv'):assert z.read('processed/'+f.name)==f.read_bytes()
        assert z.read('processed/processed-data.json')==(PUBLIC/'processed-data.json').read_bytes()
        readme=z.read('README.md').decode('utf-8')
        for link in re.findall(r'\]\(([^)]+)\)',readme):
            if not re.match(r'https?://',link):assert link in z.namelist()
    report={'owner':'A Lead','version':'1.0','status':'passed','updated':'2026-10-28','workbook':str(BOOK.relative_to(ROOT)).replace('\\','/'),'workbook_sha256':sha(BOOK),
            'package':str(PACK.relative_to(ROOT)).replace('\\','/'),'package_sha256':sha(PACK),'processed_data_sha256':sha(PUBLIC/'processed-data.json'),
            'sheets':12,'filtered_tables':14,'charts':1,'chart_series':2,'formulas':formula_count,'formula_errors':0,'formula_caches_present':True,
            'sources':6,'downloaded_files_unique':26,'raw_public_files_in_package':25,'participant_file_excluded':True,'participant_rows_exported':0,
            'microdata_shape':[926,74],'bdi_nonmissing':918,'bdi_missing':8,'bdi_unweighted_mean':mean,'sampling_kish_approx':kish,
            'year_groups':31,'year_studies_total':439,'year_sample_total':1497524,'screening_rows':52,'association_rows':73,'ai_trials':15,'ai_table_n_sum':1901,
            'native_excel_execution':'not performed','new_meta_analysis':'not performed; effect estimates extracted from publications','business_database_access':False}
    (ROOT/'docs/test/literature-data-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
