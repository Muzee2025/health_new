"""Offline, source-complete support-AI evaluation. Never contacts a provider.

Inputs are synthetic cases, separately captured responses and independent human
ratings. A demo only checks the evaluation plumbing, not model effectiveness.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median


def read_jsonl(path):
    values = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid JSON at line {number}") from None
        if not isinstance(item, dict):
            raise ValueError(f"Expected an object at line {number}")
        values.append(item)
    if not values:
        raise ValueError("Input is empty")
    return values


def unique(items, key):
    result = {}
    for item in items:
        identifier = key(item)
        if identifier in result:
            raise ValueError("Duplicate evaluation identifier")
        result[identifier] = item
    return result


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def evaluate(cases, responses, ratings):
    cases_by_id = unique(cases, lambda c: c["id"])
    for case in cases:
        checks = case.get("checks")
        if (case.get("synthetic") is not True or not isinstance(checks, list)
                or not checks or len(set(checks)) != len(checks)
                or any(not isinstance(x, str) or not x for x in checks)):
            raise ValueError("Cases require synthetic provenance and unique checks")
    response_by_key = unique(responses, lambda r: (r["variant"], r["case_id"]))
    rating_by_key = unique(ratings, lambda r: (r["variant"], r["case_id"]))
    if set(response_by_key) != set(rating_by_key):
        raise ValueError("Every response needs one independent rating")
    variants = sorted({v for v, _ in response_by_key})
    if not variants or any(not isinstance(v, str) or not v for v in variants):
        raise ValueError("Variant names are required")
    expected = {(v, c) for v in variants for c in cases_by_id}
    if set(response_by_key) != expected:
        raise ValueError("Each variant must cover exactly the same complete case set")
    summaries = []
    for variant in variants:
        latencies, decisions, errors = [], Counter(), Counter()
        tokens_in, tokens_out, token_records = 0, 0, 0
        for case_id, case in cases_by_id.items():
            response = response_by_key[variant, case_id]
            rating = rating_by_key[variant, case_id]
            if response.get("status") not in {"ok", "error", "timeout"}:
                raise ValueError("Unknown response status")
            if not valid_number(response.get("latency_ms")):
                raise ValueError("Every attempted request needs finite nonnegative latency")
            if response["status"] == "ok" and not str(response.get("text", "")).strip():
                raise ValueError("Successful responses need captured output")
            errors[response["status"]] += 1
            latencies.append(response["latency_ms"])
            checks = rating.get("checks", {})
            if set(checks) != set(case["checks"]):
                raise ValueError("Rating checks do not match the case rubric")
            if not str(rating.get("reviewer", "")).strip():
                raise ValueError("Ratings need a reviewer identifier")
            if any(value not in {"pass", "fail", "not_applicable", "unreviewed"}
                   for value in checks.values()):
                raise ValueError("Unknown rating decision")
            decisions.update(checks.values())
            usage = response.get("usage")
            if usage is not None:
                if (not isinstance(usage, dict)
                        or any(type(usage.get(k)) is not int or usage[k] < 0
                               for k in ("input_tokens", "output_tokens"))):
                    raise ValueError("Usage must contain actual nonnegative integer counts")
                tokens_in += usage["input_tokens"]
                tokens_out += usage["output_tokens"]
                token_records += 1
        reviewed = decisions["pass"] + decisions["fail"]
        complete = decisions["unreviewed"] == 0 and reviewed > 0
        ordered = sorted(latencies)
        summaries.append({
            "variant": variant, "attempted_cases": len(cases),
            "completed_responses": errors["ok"], "timeouts": errors["timeout"],
            "errors": errors["error"], "completion_rate": errors["ok"] / len(cases),
            "latency_all_attempts_ms": {"p50": median(ordered),
                "p95_nearest_rank": ordered[math.ceil(.95 * len(ordered)) - 1]},
            "human_check_counts": dict(decisions), "human_review_complete": complete,
            "human_check_pass_rate": decisions["pass"] / reviewed if complete else None,
            "usage_records": token_records,
            "total_input_tokens": tokens_in if token_records else None,
            "total_output_tokens": tokens_out if token_records else None,
        })
    demo = any(r.get("synthetic_response") is True for r in responses)
    professional_review = all(c.get("review_status") == "professionally_reviewed" for c in cases)
    return {"schema_version": 1, "case_count": len(cases),
            "evaluation_type": "synthetic_pipeline_demo" if demo else "captured_outputs_with_human_ratings",
            "professional_case_review_complete": professional_review,
            "clinical_effectiveness_established": False,
            "comparable_human_checks": all(s["human_review_complete"] for s in summaries),
            "cost_estimate": None, "variants": summaries,
            "limitations": ["Rubric compliance is not diagnostic accuracy or clinical benefit.",
                "Latency includes failed attempts and uses nearest-rank p95.",
                "Token totals require provider usage; no prices or costs are invented.",
                "Real provider outputs and professional case review are separate prerequisites."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--responses", required=True, type=Path)
    parser.add_argument("--ratings", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(read_jsonl(args.cases), read_jsonl(args.responses), read_jsonl(args.ratings))
        if args.output.exists():
            raise ValueError("Refusing to overwrite evaluation evidence")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        print(json.dumps({"status": "ok", "cases": report["case_count"],
                          "variants": len(report["variants"]), "type": report["evaluation_type"]}))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Evaluation rejected ({type(exc).__name__}); check inputs and output path.\n")


if __name__ == "__main__":
    main()
