import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("support_ai_eval", Path(__file__).parents[1] / "evaluate-support-ai.py")
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases = [{"id": "a", "synthetic": True, "checks": ["grounded"]}]
        self.responses = [{"case_id": "a", "variant": "baseline", "status": "timeout", "latency_ms": 1000}]
        self.ratings = [{"case_id": "a", "variant": "baseline", "reviewer": "test", "checks": {"grounded": "fail"}}]

    def test_failed_attempt_in_denominator(self):
        report = evaluation.evaluate(self.cases, self.responses, self.ratings)
        self.assertEqual(report["variants"][0]["completion_rate"], 0)
        self.assertEqual(report["variants"][0]["human_check_pass_rate"], 0)
        self.assertFalse(report["clinical_effectiveness_established"])

    def test_missing_case_or_duplicate_cannot_improve_comparison(self):
        for responses in ([], self.responses * 2, [dict(self.responses[0], case_id="unknown")]):
            with self.assertRaises((ValueError, KeyError)):
                evaluation.evaluate(self.cases, responses, self.ratings)

    def test_unreviewed_does_not_become_pass(self):
        self.ratings[0]["checks"]["grounded"] = "unreviewed"
        report = evaluation.evaluate(self.cases, self.responses, self.ratings)
        self.assertIsNone(report["variants"][0]["human_check_pass_rate"])
        self.assertFalse(report["comparable_human_checks"])

    def test_nan_and_boolean_are_not_measurements(self):
        for value in (float("nan"), float("inf"), True, -1):
            with self.assertRaises(ValueError):
                evaluation.evaluate(self.cases, [dict(self.responses[0], latency_ms=value)], self.ratings)

    def test_different_variant_coverage_is_rejected(self):
        self.cases.append({"id": "b", "synthetic": True, "checks": ["grounded"]})
        with self.assertRaises(ValueError):
            evaluation.evaluate(self.cases, self.responses, self.ratings)

    def test_demo_is_explicit_and_usage_is_not_invented(self):
        self.responses[0]["synthetic_response"] = True
        report = evaluation.evaluate(self.cases, self.responses, self.ratings)
        self.assertEqual(report["evaluation_type"], "synthetic_pipeline_demo")
        self.assertIsNone(report["variants"][0]["total_input_tokens"])
        self.assertIsNone(report["cost_estimate"])


if __name__ == "__main__":
    unittest.main()
