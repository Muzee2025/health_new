"""Package public questionnaire research; never reads application data or config."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs/plan/questionnaire-research-20261029"
OUTPUT = ROOT / "deliverables/心域智链_心理问卷选型与上线准备资料_20261029.zip"
DATE = "2026-10-29"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = []
    for group in ("instruments", "governance"):
        doc = json.loads((RESEARCH / group / "sources.json").read_text(encoding="utf-8"))
        for source in doc["sources"]:
            url = source["url"]
            if not url.startswith(("https://", "project-file:")):
                raise ValueError(f"Unsupported source URL: {source['id']}")
            rows.append({
                "group": group, "source_id": source["id"], "title": source["title"],
                "url": url, "source_type": source.get("kind", source.get("issuer", "")),
                "publication_date_or_period": source.get("date", ""),
                "research_date": DATE, "evidence_summary": source.get("evidence", ""),
                "unresolved": source.get("unresolved", "See associated research note"),
            })
    write_csv(RESEARCH / "source-catalog.csv", list(rows[0]), rows)
    write_csv(RESEARCH / "questionnaire-register-template.csv", [
        "instrument_id", "instrument_name", "instrument_version", "language_and_region",
        "respondent_type", "target_age_range", "purpose", "recall_period", "item_count",
        "source_url", "rights_holder", "license_url_or_evidence", "license_allowed_use",
        "translation_rights", "digital_commercial_conditions", "scoring_version",
        "reverse_item_rule_reference", "missing_item_rule_reference", "conversion_and_rounding",
        "threshold_and_population_evidence", "interpretation_version", "professional_reviewer",
        "consent_notice_version", "safety_response_reference", "approved_artifact_sha256",
        "decision_status", "review_date",
    ], [])
    task_data = [
        ("QNR-01", "P0", "范围与实际年龄", "学校项目/专业负责人", "明确高校成人、未成年或初高中场景及测量用途"),
        ("QNR-02", "P0", "具体工具与正式中文版本", "心理专业负责人", "题本来源、版本、填写者、适用证据及负担评估"),
        ("QNR-03", "P0", "使用权利", "项目/法务/采购", "逐工具记录允许用途、电子化/商业/译本条件及授权材料"),
        ("QNR-04", "P0", "计分与解释规范", "心理专业负责人", "反向题、缺项、转换/取整、阈值、结果措辞与用途边界"),
        ("QNR-05", "P0", "分龄告知与处理基础", "校方法务/隐私负责人", "处理基础、敏感信息告知、适用同意、监护参与和退出"),
        ("QNR-06", "P0", "人工承接", "心理服务/校内运营", "主责/替补、时段、响应规则、风险题项及转介与离线流程"),
        ("QNR-07", "P0", "影响评估与供应链", "校方隐私/网安/采购", "PIPIA、委托/接收方、日志/训练/留存、跨境实际链路"),
        ("QNR-08", "P0", "服务端计分", "后端负责人", "新隔离库/合成数据下重新计分，拒绝客户端伪造与异常答卷"),
        ("QNR-09", "P0", "版本化记录", "后端/专业负责人", "题本/计分/解释/告知版本关联，历史未知不伪填"),
        ("QNR-10", "P0", "草稿和共享设备", "前端/隐私负责人", "过期、退出/切换账号、版本失效与合成会话验证"),
        ("QNR-11", "P0", "访问与导出", "后端/网安负责人", "按真实分配权限、小组反推防护、导出审批及审计"),
        ("QNR-12", "P1", "AI辅助解释", "AI/专业/隐私负责人", "最小输入、固定版本、依据与错误评测，禁止改计分和自动诊断"),
        ("QNR-13", "P1", "技术演练", "测试/运营负责人", "合成边界、缺项、通知失败、夜间、撤回、停用与恢复"),
        ("QNR-14", "P1", "试点与专业验证", "学校项目/专业/伦理责任人", "按任务决定研究设计、审批、分母/不确定性、停止条件"),
        ("QNR-15", "P1", "复核来源与发布决定", "实际学校责任角色", "上线前重查政策/许可与题本；技术、专业、隐私、运营分别确认"),
    ]
    checklist = [{"task_id": a, "priority": b, "work_package": c, "responsible_role": d,
                  "required_evidence": e, "actual_person": "待填写", "status": "待实施或确认",
                  "evidence_path": "", "confirmation_date": ""} for a, b, c, d, e in task_data]
    write_csv(RESEARCH / "launch-checklist.csv", list(checklist[0]), checklist)

    # Files are explicitly enumerated; do not accidentally package other work or data.
    names = ["README.md", "问卷使用问题与答疑.md", "code-observations.md", "source-catalog.csv",
             "questionnaire-register-template.csv", "launch-checklist.csv",
             "instruments/instruments.md", "instruments/sources.json",
             "governance/governance.md", "governance/sources.json"]
    payloads = {}
    mappings = []
    for name in names:
        path = RESEARCH / name
        original = path.read_bytes()
        exported = original
        if path.suffix == ".md":
            # A standalone evidence pack does not distribute the application's source code.
            # Turn repository-only links into explicit path references, retaining internal links.
            def convert(match):
                target = match.group(2)
                if "://" in target or target.startswith("#"):
                    return match.group(0)
                file_part, _, anchor = target.partition("#")
                resolved = (path.parent / file_part).resolve()
                if not resolved.is_relative_to(RESEARCH.resolve()):
                    rel = resolved.relative_to(ROOT.resolve()).as_posix()
                    return f"{match.group(1)}（仓库路径：`{rel}{'#' + anchor if anchor else ''}`）"
                return match.group(0)
            exported = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", convert,
                              original.decode("utf-8")).encode("utf-8")
        payloads[name] = exported
        mappings.append({"path": name, "source_sha256": digest(original),
                         "packaged_sha256": digest(exported),
                         "repository_links_rendered_as_paths": exported != original})
    note = ("本资料包只含公开来源摘要、工具元数据与准备清单，不含完整量表、研究个体数据、"
            "学生答卷、应用源码或运行配置。README.md为入口；各来源原文与许可仍需在选型/上线时复核。"
            "仓库上下文以路径文字保留，独立解压包不含这些源码/历史文件。\n")
    payloads["阅读说明.txt"] = note.encode("utf-8")
    external = {r["url"] for r in rows if r["url"].startswith("https://")}
    manifest = {"owner": "A", "version": "1.0", "status": "research_pack_only",
                "updated": DATE, "source_entries": len(rows), "unique_external_urls": len(external),
                "local_project_context_entries": sum(r["url"].startswith("project-file:") for r in rows),
                "full_questionnaires_included": False, "real_responses_included": False,
                "source_files": mappings,
                "files": [{"path": n, "sha256": digest(b), "bytes": len(b)} for n, b in payloads.items()]}
    manifest_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (RESEARCH / "manifest.json").write_bytes(manifest_data)
    payloads["manifest.json"] = manifest_data
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in payloads.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    with zipfile.ZipFile(OUTPUT) as bundle:
        assert bundle.testzip() is None
        for entry in manifest["files"]:
            assert digest(bundle.read(entry["path"])) == entry["sha256"]
    print(json.dumps({"output": str(OUTPUT), "source_entries": len(rows),
                      "unique_external_urls": len(external), "files": len(payloads),
                      "sha256": digest(OUTPUT.read_bytes())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
