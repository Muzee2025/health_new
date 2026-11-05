"""Verify the delivered data dictionary against read-only schema evidence and XLSX XML."""
import hashlib
import json
import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "tmp/data-inventory-20261028"
BOOK = ROOT / "deliverables/心域智链_数据库变量与项目数据_20261028.xlsx"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def main():
    evidence = json.loads((WORK / "inventory.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(BOOK) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(n.itertext()) for n in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        def cell(node):
            v = node.find("m:v", NS)
            if node.get("t") == "s":
                return strings[int(v.text)]
            if node.get("t") == "inlineStr":
                return "".join(node.find("m:is", NS).itertext())
            if v is None:
                return None
            if node.get("t") == "e":
                raise AssertionError("Spreadsheet error cell")
            try:
                return float(v.text)
            except (ValueError, TypeError):
                return v.text
        paths = sorted((p for p in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", p)), key=lambda x: int(re.search(r"sheet(\d+)", x).group(1)))
        sheets = [{c.get("r"): cell(c) for c in ET.fromstring(z.read(p)).findall(".//m:sheetData/m:row/m:c", NS)} for p in paths]
        fields = {(sheets[1][f"B{r}"], sheets[1][f"C{r}"]) for r in range(7, 205)}
        preview = evidence["databases"][0]
        expected_fields = {(t["name"], c["name"]) for t in preview["tables"] for c in t["columns"]}
        assert fields == expected_fields and len(fields) == 198
        models = {(t, c) for t, columns in evidence["models"].items() for c in columns}
        assert fields == models
        raw_regions = evidence["regional"]
        for r, original in enumerate(raw_regions, 7):
            assert sheets[5][f"A{r}"] == original["region"]
            keys = ["year", "regular_vocational_heis", "academic_bachelor_students", "vocational_normal_short_students", "normal_vocational_undergraduates", "regular_senior_students", "junior_students"]
            for column, key in zip("BCDEFGH", keys):
                assert sheets[5][f"{column}{r}"] == original[key]
            assert sheets[5][f"L{r}"] == 0
        values = [r["normal_vocational_undergraduates"] for r in raw_regions]
        total = sum(values)
        avg = total / len(values)
        cv = math.sqrt(sum((n - avg) ** 2 for n in values) / len(values)) / avg
        cr5 = sum(sorted(values, reverse=True)[:5]) / total
        assert sheets[0]["B16"] == 198 and sheets[0]["B17"] == 0 and sheets[0]["B18"] == 8
        assert sheets[0]["B19"] == total
        assert math.isclose(sheets[0]["B20"], cr5, abs_tol=1e-12)
        assert math.isclose(sheets[0]["B21"], cv, abs_tol=1e-12)
        assert math.isclose(sheets[0]["B22"], 11.26, abs_tol=1e-12)
        formula_count = 0
        for p in paths:
            for c in ET.fromstring(z.read(p)).findall(".//m:c", NS):
                if c.find("m:f", NS) is not None:
                    formula_count += 1
                    assert c.find("m:v", NS) is not None, "Missing cached calculation"
        table_paths = [p for p in z.namelist() if re.fullmatch(r"xl/tables/table\d+\.xml", p)]
        assert len(table_paths) == 7
        for p in table_paths:
            assert ET.fromstring(z.read(p)).find("m:autoFilter", NS) is not None
        json_rows = sheets[4]
        matches = [r for r in range(7, 80) if json_rows.get(f"C{r}") == "score_distribution"]
        assert len(matches) == 1 and json_rows[f"D{matches[0]}"] == "object"
        # Check well-known credential encodings without printing any offending value.
        assert not any(re.search(r"\$2[aby]\$\d{2}\$|\$argon2(?:id|i|d)\$", s) for s in strings)
        chart_paths = [p for p in z.namelist() if re.fullmatch(r"xl/(?:drawings/)?charts/chart\d+\.xml", p)]
        assert len(chart_paths) == 1
        assert '0.0,,"百万"' in z.read(chart_paths[0]).decode("utf-8") or '0.0,,&quot;百万&quot;' in z.read(chart_paths[0]).decode("utf-8")
    unchanged = []
    for d in evidence["databases"]:
        digest = hashlib.sha256((ROOT / d["path"]).read_bytes()).hexdigest()
        unchanged.append(digest == d["sha256_before"] == d["sha256_after"])
    assert all(unchanged)
    report = {"owner": "A Lead", "version": "1.0", "status": "passed", "updated": "2026-10-28",
              "workbook": str(BOOK.relative_to(ROOT)).replace("\\", "/"), "sha256": hashlib.sha256(BOOK.read_bytes()).hexdigest(),
              "source_database_count": len(unchanged), "source_database_bytes_unchanged": all(unchanged), "sheets": len(sheets), "filtered_tables": len(table_paths),
              "dictionary_fields": len(fields), "formula_count": formula_count, "formula_errors": 0, "formula_caches_present": True,
              "regional_total": total, "regional_cr5": cr5, "regional_cv": cv, "regional_identity_differences": 0,
              "legacy_fk_issues": [{"source_id": d["source_id"], **issue} for d in evidence["databases"] for issue in d["foreign_key_issues"]],
              "current_service_database_binding": "not_verified", "external_provider_calls": 0,
              "privacy": "schema and aggregate counts only; no individual row values", "native_excel_execution": "not_performed"}
    (ROOT / "docs/test/database-inventory-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
