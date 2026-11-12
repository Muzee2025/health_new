"""Create a new training DB containing original AI-authored candidate dialogues.

Copies the verified reference package read-only, never opens application DBs,
loads .env, calls providers, or starts training. Existing output is rejected.
"""
from __future__ import annotations  # noqa: I001

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("reference_builder", ROOT / "scripts/build-training-database.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)
BATCH_ID = "synthetic-qa-20261102-v1"
BASE_SHA256 = "55f8826176edd2697ccb48f7e3d158149f5cb0fafdd248a396dbe4177e2e9ab3"
SOURCE_NAMES = ("part-a.jsonl", "part-b.jsonl", "part-c.jsonl")
TOPICS = {
    "study_pressure": "学习压力", "time_management": "时间安排",
    "career_uncertainty": "升学与职业不确定", "perfectionism": "完美主义",
    "relationships": "人际相处", "loneliness": "孤独与融入",
    "family_boundaries": "家庭沟通与边界", "emotion_support": "情绪支持",
    "routine_and_helpseeking": "日常状态与寻求帮助", "assessment_literacy": "测评解读边界",
    "platform_privacy": "平台使用与隐私", "safety_support": "安全求助",
}
COPY_TABLES = ("source_files", "source_sheets", "source_cells", "reference_records",
               "schema_tables", "schema_fields", "region_education", "literature_aggregates", "training_examples")
GUIDANCE = [
    {"publisher": "NIMH", "title": "I'm So Stressed Out!", "url": "https://www.nimh.nih.gov/health/publications/so-stressed-out-fact-sheet"},
    {"publisher": "NIMH", "title": "5 Action Steps to Help Someone Having Thoughts of Suicide",
     "url": "https://www.nimh.nih.gov/health/publications/5-action-steps-to-help-someone-having-thoughts-of-suicide"},
    {"publisher": "WHO", "title": "Doing What Matters in Times of Stress", "url": "https://www.who.int/publications/i/item/9789240003927"},
]
OLD_COUNT = "supervised_examples INTEGER NOT NULL CHECK(supervised_examples = 0)"
assert REFERENCE.DDL.count(OLD_COUNT) == 1
DDL = REFERENCE.DDL.replace(OLD_COUNT, "candidate_examples INTEGER NOT NULL CHECK(candidate_examples >= 0)") + """
CREATE TABLE synthetic_batches (
 id TEXT PRIMARY KEY, created_at TEXT NOT NULL, generation_method TEXT NOT NULL,
 candidate_examples INTEGER NOT NULL, scenario_count INTEGER NOT NULL,
 accepted_examples INTEGER NOT NULL CHECK(accepted_examples=0),
 professional_reviewed INTEGER NOT NULL CHECK(professional_reviewed=0),
 training_started INTEGER NOT NULL CHECK(training_started=0),
 guidance_json TEXT NOT NULL CHECK(json_valid(guidance_json))
);
CREATE TABLE synthetic_example_metadata (
 example_id TEXT PRIMARY KEY REFERENCES training_examples(id),
 batch_id TEXT NOT NULL REFERENCES synthetic_batches(id),
 topic TEXT NOT NULL, scenario_id TEXT NOT NULL, turn_index INTEGER NOT NULL CHECK(turn_index IN(1,2)),
 author_agent TEXT NOT NULL, author_model_id TEXT NOT NULL,
 generation_method TEXT NOT NULL CHECK(generation_method='ai_authored_fictional_dialogue'),
 professional_reviewed INTEGER NOT NULL CHECK(professional_reviewed=0),
 UNIQUE(batch_id,scenario_id,turn_index)
);
"""


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def load_records(source_dir):
    records, sources = [], []
    for name in SOURCE_NAMES:
        path = Path(source_dir) / name
        if path.is_symlink():
            raise ValueError("Synthetic source must be a regular local file")
        raw_bytes = path.read_bytes()
        source_digest = hashlib.sha256(raw_bytes).hexdigest()
        raw = raw_bytes.decode("utf-8")
        lines = raw.splitlines()
        source_records = []
        for index, line in enumerate(lines, 1):
            if not line.strip():
                raise ValueError("Blank JSONL line")
            item = json.loads(line)
            if not isinstance(item, dict) or set(item) != {"id", "topic", "scenario_id", "turn_index", "history", "question", "answer"}:
                raise ValueError("Unexpected authored source keys")
            item["_source_file"], item["_source_line"] = name, index
            source_records.append(item)
        if len(source_records) != 32:
            raise ValueError("Each authored source must have 32 pairs")
        records.extend(source_records)
        sources.append({"filename": name, "sha256": source_digest, "candidate_examples": len(source_records),
                        "author_agent": {"part-a.jsonl": "dashboard_polish", "part-b.jsonl": "report_polish", "part-c.jsonl": "root"}[name],
                        "author_model_id": "unknown", "editor_agent": "root",
                        "revision_note": {"part-a.jsonl": "removed unnecessary campus-location question",
                                          "part-b.jsonl": "removed 24 unnecessary age prefixes; refreshed matching history",
                                          "part-c.jsonl": "original authored content"}[name]})
    validate_records(records)
    return records, sources


def validate_records(records):
    if len(records) != 96:
        raise ValueError("Batch must contain 96 pairs")
    expected_keys = {"id", "topic", "scenario_id", "turn_index", "history", "question", "answer", "_source_file", "_source_line"}
    seen_ids, seen_questions, seen_answers = set(), set(), set()
    scenarios = defaultdict(list)
    for item in records:
        if set(item) != expected_keys:
            raise ValueError("Unexpected source keys")
        for key in ("id", "topic", "scenario_id", "question", "answer"):
            if not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 3000:
                raise ValueError("Missing or invalid text: " + key)
        if item["topic"] not in TOPICS:
            raise ValueError("Unknown topic")
        if not re.fullmatch(r"qa-[abc]-\d{3}", item["id"]):
            raise ValueError("Invalid synthetic record ID")
        if item["id"] in seen_ids:
            raise ValueError("Duplicate ID")
        seen_ids.add(item["id"])
        for key, seen in (("question", seen_questions), ("answer", seen_answers)):
            value = normalized(item[key])
            if not value or value in seen:
                raise ValueError("Normalized duplicate " + key)
            seen.add(value)
        if type(item["turn_index"]) is not int or item["turn_index"] not in (1, 2):
            raise ValueError("Invalid turn index")
        if not isinstance(item["history"], list):
            raise ValueError("Invalid history")
        scenarios[item["scenario_id"]].append(item)
    if Counter(r["topic"] for r in records) != Counter({topic: 8 for topic in TOPICS}):
        raise ValueError("Topic coverage differs from 12 x 8")
    if len(scenarios) != 72:
        raise ValueError("Expected 72 independent scenario groups")
    shapes = defaultdict(Counter)
    for scenario_id, turns in scenarios.items():
        if [r["turn_index"] for r in turns] not in ([1], [1, 2]):
            raise ValueError("Scenario turn order must be 1 or 1,2")
        if len({r["topic"] for r in turns}) != 1 or len({r["_source_file"] for r in turns}) != 1:
            raise ValueError("Scenario crosses topic or author source")
        history = []
        for item in turns:
            if item["history"] != history:
                raise ValueError("History differs from previous scenario turns: " + scenario_id)
            history.extend([{"role": "user", "content": item["question"]}, {"role": "assistant", "content": item["answer"]}])
        shapes[turns[0]["topic"]][len(turns)] += 1
    if any(shape != Counter({1: 4, 2: 2}) for shape in shapes.values()):
        raise ValueError("Each topic needs four single-turn and two two-turn scenarios")


def copy_reference(connection, reference_package):
    package = Path(reference_package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    path = package / "training-reference.sqlite3"
    if sha256(path) != BASE_SHA256 or manifest["files"][path.name]["sha256"] != BASE_SHA256:
        raise ValueError("Reference database differs from verified package")
    source = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        source.execute("PRAGMA query_only=ON")
        connection.executescript(DDL)
        if source.execute("SELECT COUNT(*) FROM training_examples").fetchone()[0] != 0:
            raise ValueError("Reference package unexpectedly contains training rows")
        for table in COPY_TABLES:
            rows = source.execute('SELECT * FROM "' + table + '"').fetchall()
            columns = [r[1] for r in source.execute('PRAGMA table_info("' + table + '")')]
            if table == "source_files":
                columns = ["candidate_examples" if c == "supervised_examples" else c for c in columns]
            sql = 'INSERT INTO "' + table + '" (' + ','.join('"' + c + '"' for c in columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')'
            connection.executemany(sql, rows)
    finally:
        source.close()
    return path


def quality_profile(records):
    pairs = []
    for index, first in enumerate(records):
        for second in records[index + 1:]:
            qr = SequenceMatcher(None, normalized(first["question"]), normalized(second["question"]), autojunk=False).ratio()
            ar = SequenceMatcher(None, normalized(first["answer"]), normalized(second["answer"]), autojunk=False).ratio()
            if qr >= 0.86 or ar >= 0.86:
                pairs.append({"first": first["id"], "second": second["id"],
                              "question_ratio": round(qr, 4), "answer_ratio": round(ar, 4)})
    return {"candidate_examples": len(records), "scenario_groups": len({r["scenario_id"] for r in records}),
            "topic_counts": dict(Counter(r["topic"] for r in records)),
            "unique_normalized_questions": len({normalized(r["question"]) for r in records}),
            "unique_normalized_answers": len({normalized(r["answer"]) for r in records}),
            "near_duplicate_method": "character SequenceMatcher >= 0.86 on normalized question OR answer; heuristic only",
            "near_duplicate_candidates": pairs, "clinical_quality_assessed": False,
            "professional_reviewed": False, "accepted_for_training": 0, "split": "unassigned"}


def populate_dialogues(connection, records, sources):
    connection.execute("INSERT INTO synthetic_batches VALUES (?,?,?,?,?,0,0,0,?)", (
        BATCH_ID, datetime.now(timezone.utc).isoformat(), "ai_authored_fictional_dialogue", len(records),
        len({r["scenario_id"] for r in records}), encode(GUIDANCE)))
    source_map = {}
    for source in sources:
        source_id = "ai-synthetic:" + source["sha256"]
        source_map[source["filename"]] = (source_id, source)
        connection.execute("INSERT INTO source_files VALUES (?,?,?,?,?,?)", (
            source_id, source["filename"], source["sha256"], "2026-11-02", "ai_synthetic_candidate", source["candidate_examples"]))
    exported = []
    for record in records:
        source_id, source = source_map[record["_source_file"]]
        example_id = BATCH_ID + ":" + record["id"]
        group_id = BATCH_ID + ":" + record["scenario_id"]
        inputs = {"messages": record["history"] + [{"role": "user", "content": record["question"]}]}
        target = {"role": "assistant", "content": record["answer"]}
        content_hash = hashlib.sha256(encode([inputs, target]).encode("utf-8")).hexdigest()
        connection.execute("INSERT INTO training_examples VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
            example_id, source_id, "conversation", encode(inputs), encode(target), group_id, 1,
            "ai_synthetic_authored", "candidate", content_hash, "unassigned"))
        connection.execute("INSERT INTO synthetic_example_metadata VALUES (?,?,?,?,?,?,?,?,0)", (
            example_id, BATCH_ID, record["topic"], record["scenario_id"], record["turn_index"],
            source["author_agent"], source["author_model_id"], "ai_authored_fictional_dialogue"))
        exported.append({"id": example_id, "messages": inputs["messages"] + [target], "metadata": {
            "source_id": source_id, "source_file": source["filename"], "source_sha256": source["sha256"],
            "source_line": record["_source_line"], "topic": record["topic"], "scenario_id": record["scenario_id"],
            "group_id": group_id, "turn_index": record["turn_index"], "synthetic": True,
            "generation_method": "ai_authored_fictional_dialogue", "author_agent": source["author_agent"],
            "author_model_id": source["author_model_id"], "quality_status": "candidate",
            "professional_reviewed": False, "label_origin": "ai_synthetic_authored", "content_sha256": content_hash,
            "split": "unassigned"}})
    return exported


def dataset_card(profile):
    lines = ["> owner: A ｜ version: 1.0 ｜ status: AI合成候选已入库，未经专业审核 ｜ updated: 2026-11-02",
             "", "# 心域智链合成问答数据集（首批）", "",
             "本批由AI逐条原创虚构成人大学生场景，经用户明确授权生成，来源是三份part-*.jsonl，",
             "不是从Excel、学生资料、历史聊天或真人咨询中抽取，也不是文献原始样本。",
             "三名作者的运行时精确模型ID不可核验，统一如实记录unknown。", "",
             "96对问答，72个场景：48个单轮场景和24个两轮场景。每个主题8对；第二轮输入带完整前轮。",
             "scenario/group_id可用于以后按场景分组切分；本轮split全部unassigned，没有训练或评估结果。", "",
             "|主题|问答对数|", "|---|---:|"]
    lines.extend(f"|{TOPICS[topic]}|{count}|" for topic, count in profile["topic_counts"].items())
    lines.extend(["", "所有记录均为synthetic=true、quality_status=candidate、professional_reviewed=false；",
                  "主题是合成场景分类，不是诊断、临床风险等级或专家标签。当前获专业接受的训练样本为0。",
                  "一般支持/安全转介回答属于候选文本，不能据此声称模型有效或用于真实诊疗。",
                  "AI复核与自动检查不替代专业内容审核，也不是第三方专业标注。", "",
                  "`synthetic-training.sqlite3`是本轮新库，保留旧库476条reference_only资料，并新增96条training_examples。",
                  "参考资料不可写成个人监督样本的触发器保留。新source_files.candidate_examples记录候选条数，",
                  "这是独立新库的列名调整，旧包的supervised_examples列、文件与manifest保持原样。", "",
                  "`training-examples.jsonl`为通用messages+metadata格式；不是训练任务提交。",
                  "`问答预览.md`逐条呈现全部96对；`source-dialogues/`保留逐条作者原稿，便于复核。",
                  "`quality-report.json`检查精确重复和相似文本；近重复指标只是字符启发式，不证明语义独立或临床质量。", "",
                  "回答边界核对参考以下公开资料，未把网页拼接为问答；这些机构未审核或背书本数据集："])
    lines.extend(f"- [{g['publisher']}：{g['title']}]({g['url']})" for g in GUIDANCE)
    lines.extend(["", "只读SQL示例：", "", "```sql",
                  "SELECT COUNT(*) FROM training_examples; -- 96",
                  "SELECT topic,COUNT(*) FROM synthetic_example_metadata GROUP BY topic;",
                  "SELECT quality_status,split,COUNT(*) FROM training_examples GROUP BY quality_status,split;",
                  "SELECT id,input_json,target_json FROM training_examples ORDER BY id LIMIT 5;", "```", "",
                  "新库与原业务库独立，未创建真实账号、分配、预警或测评记录，未切换网站数据。",
                  "未使用真实提供商、训练或上传。需要扩充时继续登记新的合成批次，不能把本批候选冒称真人咨询记录。", ""])
    return "\n".join(lines)


def build(reference_package, source_dir, output):
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output must be a new directory")
    records, sources = load_records(source_dir)
    profile = quality_profile(records)
    with sqlite3.connect(":memory:") as connection:
        source_db = copy_reference(connection, reference_package)
        exported = populate_dialogues(connection, records, sources)
        connection.commit()
        if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or connection.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Database integrity or foreign key check failed")
        if sha256(source_db) != BASE_SHA256 or any(sha256(Path(source_dir) / s["filename"]) != s["sha256"] for s in sources):
            raise ValueError("Input changed during build")
        output.mkdir(parents=True, exist_ok=False)
        with sqlite3.connect(output / "synthetic-training.sqlite3") as target:
            connection.backup(target)
    (output / "training-examples.jsonl").write_text("".join(encode(e) + "\n" for e in exported), encoding="utf-8")
    (output / "schema.sql").write_text(DDL, encoding="utf-8")
    (output / "数据说明.md").write_text(dataset_card(profile), encoding="utf-8")
    (output / "quality-report.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_output = output / "source-dialogues"
    source_output.mkdir()
    for source in sources:
        (source_output / source["filename"]).write_bytes((Path(source_dir) / source["filename"]).read_bytes())
    preview = ["> owner: A ｜ version: 1.0 ｜ status: AI合成候选逐条预览 ｜ updated: 2026-11-02", "", "# 96组虚拟问答", "", "所有人物和经历均为虚构；未经专业审核。双轮场景第二条继承前一条上下文。", ""]
    for r in records:
        preview.extend([f"## {r['id']} · {TOPICS[r['topic']]} · {r['scenario_id']} 第{r['turn_index']}轮", "",
                        "问：" + r["question"], "", "答：" + r["answer"], ""])
    (output / "问答预览.md").write_text("\n".join(preview), encoding="utf-8")
    manifest = {"batch_id": BATCH_ID, "created_for": "2026-11-02", "source_type": "ai_synthetic_candidate",
                "candidate_examples": 96, "scenario_groups": 72, "reference_records_preserved": 476,
                "accepted_examples": 0, "professional_reviewed": False, "training_started": False,
                "source_database_sha256": BASE_SHA256, "author_sources": sources, "guidance": GUIDANCE,
                "files": {p.relative_to(output).as_posix(): {"sha256": sha256(p), "bytes": p.stat().st_size}
                          for p in sorted(output.rglob("*")) if p.is_file()}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-package", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.reference_package, args.source_dir, args.output)
    print(encode({key: manifest[key] for key in ("candidate_examples", "scenario_groups", "accepted_examples", "training_started")}))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
