"""Package public article aggregates while explicitly excluding participant XLSX."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'tmp/literature-data-20261028'
PUBLIC=ROOT/'docs/plan/research-data-20261028'
OUTPUT=ROOT/'deliverables/心域智链_公开文献数据包_20261028.zip'


def main():
    data=json.loads((PUBLIC/'processed-data.json').read_text(encoding='utf-8'))
    package_readme='''# 心域智链公开文献数据包

> owner: A Lead ｜ version: 1.0 ｜ status: 公开聚合数据交付 ｜ updated: 2026-10-28

本资料包对应6篇定向选择的公开论文，不是系统综述。SciSpace用于发现线索，所有数值回查下载的原文/补充材料。未与项目业务用户数据合并。

## 包内数据

- [规范化JSON](processed/processed-data.json)：全部聚合数据与来源位置。
- [来源与完整书目](processed/sources.csv)：作者、题名、期刊、DOI、网址、研究设计、观察期、许可。
- [74字段字典](processed/microdata_dictionary.csv)及[20项质量聚合](processed/microdata_quality.csv)：原始访谈XLSX仅在本地处理，个体记录不在包内。
- [调查波次](processed/survey_waves.csv)、[筛查汇总](processed/screening_aggregates.csv)、[发表年份组](processed/publication_year_groups.csv)、[调整后关联](processed/adjusted_associations.csv)。
- [AI效果](processed/ai_effects.csv)、[AI亚组](processed/ai_moderators.csv)、[15行试验特征](processed/ai_trial_characteristics.csv)、[Woebot终点](processed/woebot_endpoints.csv)。
- [来源冲突](processed/source_audits.csv)、[逐文件下载凭证](provenance/source-file-manifest.json)、[SciSpace检索日志](provenance/search-log.json)。

raw_public/内25份公开原文或聚合补充材料均保留原始字节，下载凭证含URL、时间与SHA256。唯一排除的源文件是YANG2023的个体XLSX；本包不含任何个体资料、序号值或访谈日期值。

## 许可与处理

原始文章为[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)，具体第三方材料例外以原文信用行说明为准。完整书目和各文件许可在sources.csv/下载凭证中，原始资料内版权说明未改。规范化数据是本轮提取/转换的派生结果：比例存为0—1，原表空组标签作结构展开，缺失保持缺失；OR、Hedges g、SE和SD保留不同量纲。

## 影响解读的限制

两次调查为不同样本，比例差不表示同一人的变化。发表年份不是调查年份；筛查不是诊断；OR不是风险比或因果效应。各来源/亚组可能重叠，不简单相加。AI干预结果为论文原报效应，不是本项目已验证疗效或本轮重新开展的Meta分析。

926条访谈数据来自分层抽样，不直接代表6818筛查人群。BDI-II总分918条有值，8条缺失不填0。作者权重和性别标准化存在版本/口径待澄清项，因此本轮没有重新估计诊断患病率。来源冲突行保留原值，不能据此作强结论。

## 复算

code/内提供采集和处理脚本。依赖Python及lxml、python-docx、pypdf，项目采用bundled运行时；脚本以所在code目录的上一级为ROOT，重跑会建立tmp/与docs/目录。先运行collect-literature-data.py，再运行process-literature-data.py；采集脚本会重新下载包括仅本地使用的原始个体XLSX，处理脚本只输出聚合。Excel另行交付，本包不内嵌工作簿或个人文件。
'''
    with zipfile.ZipFile(OUTPUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        z.writestr('README.md',package_readme)
        for f in sorted(PUBLIC.glob('*.csv')):z.write(f,'processed/'+f.name)
        for name in ['processed-data.json','search-log.json']:
            z.write(PUBLIC/name,('processed/' if name.startswith('processed') else 'provenance/')+name)
        source_records=[]
        for r in data['datasets']['downloaded_files']:
            src=WORK/r['local_relative_path']
            assert hashlib.sha256(src.read_bytes()).hexdigest()==r['sha256']
            entry={**r,'included_in_package':src.suffix.lower()!='.xlsx'}
            source_records.append(entry)
            if entry['included_in_package']:
                z.write(src,'raw_public/'+src.name)
        z.writestr('provenance/source-file-manifest.json',json.dumps(source_records,ensure_ascii=False,indent=2))
        for name in ['collect-literature-data.py','process-literature-data.py']:
            z.write(ROOT/'scripts'/name,'code/'+name)
    with zipfile.ZipFile(OUTPUT) as z:
        names=z.namelist()
        assert not any(n.lower().endswith(('.xlsx','.db','.sqlite','.sqlite3','.env')) for n in names)
        assert sum(n.startswith('raw_public/') for n in names)==25
        assert z.testzip() is None
    print(json.dumps({'output':str(OUTPUT),'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),'bytes':OUTPUT.stat().st_size,'zip_entries':len(names),'public_raw_files':25,'participant_rows_exported':0},ensure_ascii=False))


if __name__=='__main__':main()
