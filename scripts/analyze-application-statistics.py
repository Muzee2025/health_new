#!/usr/bin/env python3
"""Reproducible descriptive statistics for 2024 regional education counts.

Uses only Python's standard library. Run from any directory; outputs are
written beside this script's designated analysis folder.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "docs/plan/ai-application/revision-20261027/regional-education-2024.csv"
OUTPUT_DIR = ROOT / "docs/plan/ai-application/sci-revision-20261027"
OUTPUT_CSV = OUTPUT_DIR / "regional-derived.csv"
OUTPUT_JSON = OUTPUT_DIR / "math-analysis.json"
OUTPUT_MD = OUTPUT_DIR / "math-analysis.md"

SERIES = {
    "本专科": "normal_vocational_undergraduates",
    "普通高中": "regular_senior_students",
    "初中": "junior_students",
}


def quantile_type7(values: list[int], p: float) -> float:
    """Linear interpolation at h=(n-1)p (R/Excel inclusive, Hyndman-Fan 7)."""
    ordered = sorted(values)
    h = (len(ordered) - 1) * p
    lo = math.floor(h)
    hi = math.ceil(h)
    return ordered[lo] + (h - lo) * (ordered[hi] - ordered[lo])


def gini(values: list[int]) -> float:
    """Population Gini from the rank-weighted sorted-sum identity."""
    ordered = sorted(values)
    n = len(ordered)
    total = sum(ordered)
    return (2 * sum((i + 1) * x for i, x in enumerate(ordered)) / (n * total)) - (n + 1) / n


def stats(values: list[int]) -> dict[str, float | int]:
    n = len(values)
    total = sum(values)
    mean = total / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in values) / n)
    ordered = sorted(values, reverse=True)
    return {
        "n_regions": n,
        "total": total,
        "mean": mean,
        "median": float(median(values)),
        "population_sd": sd,
        "cv": sd / mean if mean else 0.0,
        "q1_type7": quantile_type7(values, 0.25),
        "q3_type7": quantile_type7(values, 0.75),
        "cr5": sum(ordered[:5]) / total if total else 0.0,
        "gini": gini(values),
        "top5_regions": [
            {"region": region, "value": value}
            for region, value in sorted(
                ((r, int(v)) for r, v in zip(_REGIONS, values)),
                key=lambda item: item[1], reverse=True
            )[:5]
        ],
    }


def fmt_int(v: int | float) -> str:
    return f"{v:,.0f}"


def fmt_num(v: float, digits: int = 2) -> str:
    return f"{v:,.{digits}f}"


def main() -> None:
    global _REGIONS
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 31 or len({r["region"] for r in rows}) != 31:
        raise ValueError(f"Expected 31 unique regions, got {len(rows)} rows")
    for row in rows:
        for key in ("regular_vocational_heis", *SERIES.values(),
                    "academic_bachelor_students", "vocational_normal_short_students"):
            row[key] = int(row[key])
    _REGIONS = [r["region"] for r in rows]

    values = {name: [r[col] for r in rows] for name, col in SERIES.items()}
    summaries = {name: stats(vals) for name, vals in values.items()}
    bachelor_total = sum(r["academic_bachelor_students"] for r in rows)
    vocational_total = sum(r["vocational_normal_short_students"] for r in rows)
    combined_total = sum(r["normal_vocational_undergraduates"] for r in rows)
    school_total = sum(r["regular_vocational_heis"] for r in rows)

    derived_rows: list[dict[str, str | int]] = []
    for row in rows:
        school_count = row["regular_vocational_heis"]
        combined = row["normal_vocational_undergraduates"]
        derived_rows.append({
            "region": row["region"], "year": row["year"],
            "regular_vocational_heis": school_count,
            "academic_bachelor_students": row["academic_bachelor_students"],
            "vocational_normal_short_students": row["vocational_normal_short_students"],
            "normal_vocational_undergraduates": combined,
            "bachelor_share_within_postsecondary": row["academic_bachelor_students"] / combined,
            "vocational_share_within_postsecondary": row["vocational_normal_short_students"] / combined,
            "postsecondary_students_per_school": combined / school_count,
            "senior_students": row["regular_senior_students"],
            "junior_students": row["junior_students"],
            "rank_postsecondary": sorted(values["本专科"], reverse=True).index(combined) + 1,
            "rank_senior": sorted(values["普通高中"], reverse=True).index(row["regular_senior_students"]) + 1,
            "rank_junior": sorted(values["初中"], reverse=True).index(row["junior_students"]) + 1,
            "share_postsecondary": combined / summaries["本专科"]["total"],
            "share_senior": row["regular_senior_students"] / summaries["普通高中"]["total"],
            "share_junior": row["junior_students"] / summaries["初中"]["total"],
        })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(derived_rows[0]))
        writer.writeheader()
        writer.writerows(derived_rows)

    hubei = next(r for r in derived_rows if r["region"] == "湖北")
    result = {
        "owner": "A",
        "version": "1.0",
        "status": "复算完成，待统稿",
        "updated": "2026-10-27",
        "dataset": {"year": 2024, "regions": len(rows), "scope": "中国大陆31省份"},
        "method": {
            "sd": "population; denominator n",
            "quartiles": "linear interpolation at h=(n-1)p (type 7)",
            "cr5": "sum of five largest regional values / all-region total",
            "gini": "(2*sum(i*x_i)/(n*sum(x)))-(n+1)/n, ascending x and i=1..n",
        },
        "totals_check": {
            "regular_vocational_heis": school_total,
            "academic_bachelor_students": bachelor_total,
            "vocational_normal_short_students": vocational_total,
            "normal_vocational_undergraduates": combined_total,
            "school_count_matches_2870": school_total == 2870,
            "students_match_38912568": combined_total == 38912568,
        },
        "postsecondary_national_bachelor_share": bachelor_total / combined_total,
        "hubei": {
            "schools": hubei["regular_vocational_heis"],
            "bachelor_students": hubei["academic_bachelor_students"],
            "vocational_students": hubei["vocational_normal_short_students"],
            "postsecondary_students": hubei["normal_vocational_undergraduates"],
            "bachelor_share_within_postsecondary": hubei["bachelor_share_within_postsecondary"],
            "postsecondary_students_per_school": hubei["postsecondary_students_per_school"],
            "stages": {
                name: {
                    "value": int(hubei["normal_vocational_undergraduates"] if name == "本专科" else hubei["senior_students"] if name == "普通高中" else hubei["junior_students"]),
                    "share": float(hubei["share_postsecondary"] if name == "本专科" else hubei["share_senior"] if name == "普通高中" else hubei["share_junior"]),
                    "rank": int(hubei["rank_postsecondary"] if name == "本专科" else hubei["rank_senior"] if name == "普通高中" else hubei["rank_junior"]),
                } for name in SERIES
            },
        },
        "stage_statistics": summaries,
        "risk_group_bound": {
            "high_risk_share": 0.454,
            "no_risk_share_upper_bound_exclusive": 0.05,
            "difference_percentage_points_lower_bound_exclusive": 40.4,
            "interpretation": "差值严格大于40.4个百分点；无风险组报告为低于5%，不填入精确5%。样本分母未提供，不计算置信区间或显著性。",
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stage_lines = []
    for name, s in summaries.items():
        stage_lines.append(
            f"| {name} | {fmt_int(s['total'])} | {fmt_num(s['mean'])} | {fmt_num(s['median'])} | "
            f"{fmt_num(s['population_sd'])} | {fmt_num(s['cv'] * 100)}% | {fmt_num(s['q1_type7'])} | "
            f"{fmt_num(s['q3_type7'])} | {fmt_num(s['cr5'] * 100)}% | {fmt_num(s['gini'], 4)} |"
        )
    top5_lines = []
    for name, s in summaries.items():
        top5 = "、".join(f"{x['region']}（{x['value'] / s['total']:.1%}）" for x in s["top5_regions"])
        top5_lines.append(f"- **{name}**：前五地为{top5}；CR5={s['cr5']:.1%}，Gini={s['gini']:.4f}。")
    h = result["hubei"]
    hubei_stage = "；".join(
        f"{name}{data['value']:,}人、31地第{data['rank']}、占比{data['share']:.2%}"
        for name, data in h["stages"].items()
    )
    md = f"""<!-- owner: A | version: 1.0 | status: 复算完成，待统稿 | updated: 2026-10-27 -->
# 2024年分地区教育规模描述统计（数学分析）

## 可用于正文的精简分析

将教育部2024年31省份各学段在校生数记为 \\(x_1,\\ldots,x_{{31}}\\)。均值 \\(\\bar x=\\sum_i x_i/31\\)，中位数为排序后第16项；总体标准差 \\(SD=\\sqrt{{\\sum_i(x_i-\\bar x)^2/31}}\\)，变异系数 \\(CV=SD/\\bar x\\)。四分位数采用 \\(h=(n-1)p\\) 的线性插值法。前五份额 \\(CR5=\\sum_{{i=1}}^5x_{{(i)}}/\\sum_i x_i\\)，其中 \\(x_{{(i)}}\\) 按从大到小排列；基尼系数按升序 \\(x_{{[i]}}\\) 计算：\\(G=2\\sum_{{i=1}}^n i x_{{[i]}}/(n\\sum_i x_i)-(n+1)/n\\)。

| 学段 | 31地合计（人） | 均值 | 中位数 | 总体SD | CV | Q1 | Q3 | CR5 | Gini |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(stage_lines)}

上述结果显示，31地教育规模的地区分布存在差异：{ '、'.join(f"{name}的CV分别为{summaries[name]['cv']:.1%}" for name in SERIES) }。普通高中与初中CR5较高，说明学生规模在前五省份的份额更大；三学段的CR5与Gini量化了各自数据集的横截面集中程度。湖北的分学段规模与名次为：{hubei_stage}。湖北本专科学生中普通本科占{h['bachelor_share_within_postsecondary']:.2%}；按同口径普通、职业高校数计算，每校平均{h['postsecondary_students_per_school']:,.1f}名本专科在校生。以上指标描述教育规模及地区分布，不表示心理风险、服务需求、付费客户或收入。

对调查所报告的高风险组45.4%与无风险组低于5%，可得两组比例差严格大于40.4个百分点；因无风险组仅报告上界，不将其替换成5%作为精确观测。材料未提供各组样本分母，本分析不构造置信区间或显著性检验。

## 附录：口径、复算方法与解释边界

### 数据范围

数据为教育部2024年各地区统计表的31省份记录，不含港澳台。普通、职业本专科合计由普通本科在校生与职业本专科在校生相加；高校数采用普通、职业高校（不含成人高校）的地区数。高中、初中分别按各自统计表口径。来源链接、下载页、原始表校验值及字段定义见输入文件 `../revision-20261027/regional-education-2024.json`，原始数见同目录 `regional-education-2024.csv`。

### 指标与算法

- 合计为31地人数之和；均值除以31；中位数为排序后第16个值。
- 总体标准差使用31作分母，适用于描述这31个已列地区，不作样本标准误解释；CV为总体标准差除以均值。
- Q1、Q3按 type 7（\\(h=(n-1)p\\)，相邻次序统计量线性插值）计算。
- CR5为人数最多的5个省份人数合计除以31地总人数。
- Gini使用排序加权公式 \\(G=2\\sum i x_{{[i]}}/(n\\sum x)-(n+1)/n\\)，升序排序、秩从1开始；与双重差绝对值公式等价。数值越大表示本组31地人数分布越不均匀。
- 本专科普通本科份额=普通本科人数/(普通本科+职业本专科人数)。每校规模=同地区本专科合计/普通、职业高校数，单位为人/校；不把该比值解释为实际单校在校生均值分布或容量。
- 湖北份额以同学段31地合计为分母，排名按人数降序，名次数值无并列修正（本数据无影响湖北名次的并列）。

### 集中度描述

{chr(10).join(top5_lines)} CR5是前五地合计份额，Gini衡量31地个体值分布差异；两者均为教育人口规模的描述统计。高中、初中与高校学段分别统计，样本集合并非心理服务调查样本。

### 可复算及校验

运行 `python scripts/analyze-application-statistics.py`（本脚本仅依赖Python标准库）会重建本附录的JSON、Markdown与地区衍生CSV。输入校验应满足普通、职业高校数合计2,870所，本专科学生数合计38,912,568人；普通本科与职业本专科人数之和必须等于本专科合计。`math-analysis.json`保存未格式化的统计值，`regional-derived.csv`保存31地派生份额、名次与每校规模。

### 局限

这些是2024年行政统计数据的完整31地横截面描述，不是对个人或学校的抽样调查。地区规模不能生态推断心理风险、心理服务需求、服务可及性、收入或市场份额；不进行虚假回归，不声称全国代表性心理结论。高风险与无风险的调查比例差缺少分组样本分母，不能由该比例差推出因果、置信区间或统计显著性。跨学段比较用于展示教育规模，不能解释为同一队列的逐级转化。
"""
    OUTPUT_MD.write_text(md, encoding="utf-8")
    print(json.dumps({
        "rows": len(rows), "csv": str(OUTPUT_CSV), "json": str(OUTPUT_JSON), "markdown": str(OUTPUT_MD),
        "totals": result["totals_check"], "hubei": result["hubei"],
        "statistics": {name: {k: v for k, v in s.items() if k != "top5_regions"} for name, s in summaries.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
