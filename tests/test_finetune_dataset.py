from __future__ import annotations

import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json

from scripts.finetune.generate_customer_dataset import build_split, normalize_utterance
from scripts.finetune.validate_customer_dataset import validate_files, validate_record


class DatasetGeneratorTest(unittest.TestCase):
    def test_split_sizes_and_category_quotas(self) -> None:
        expected = {
            "train": {
                "tool_call": 440,
                "rag": 160,
                "clarification": 80,
                "error": 40,
                "transfer": 40,
                "safety": 40,
            },
            "val": {
                "tool_call": 55,
                "rag": 20,
                "clarification": 10,
                "error": 5,
                "transfer": 5,
                "safety": 5,
            },
            "test": {
                "tool_call": 55,
                "rag": 20,
                "clarification": 10,
                "error": 5,
                "transfer": 5,
                "safety": 5,
            },
        }

        for split, quotas in expected.items():
            with self.subTest(split=split):
                records = build_split(split, seed=20260712)
                self.assertEqual(len(records), sum(quotas.values()))
                self.assertEqual(
                    Counter(record["metadata"]["category"] for record in records),
                    Counter(quotas),
                )

    def test_generation_is_deterministic(self) -> None:
        self.assertEqual(
            build_split("train", seed=20260712),
            build_split("train", seed=20260712),
        )

    def test_tool_call_counts_and_exact_arguments(self) -> None:
        expected = Counter({"group_buy_progress": 220, "group_complete": 150, "balance_usage": 180})
        actual: Counter[str] = Counter()
        for split in ("train", "val", "test"):
            for record in build_split(split, seed=20260712):
                if record["metadata"]["category"] != "tool_call":
                    continue
                message = next(item for item in record["conversations"] if item["from"] == "function_call")
                call = json.loads(message["value"])
                actual[call["name"]] += 1
                if call["name"] in {"group_buy_progress", "group_complete"}:
                    self.assertEqual(set(call["arguments"]), {"user_id", "team_id"})
                else:
                    self.assertEqual(set(call["arguments"]), {"user_id"})
        self.assertEqual(actual, expected)

    def test_progress_arithmetic_is_consistent(self) -> None:
        for record in build_split("train", seed=20260712):
            if record["metadata"]["scenario"] != "group_buy_progress":
                continue
            expected = record["metadata"]["expected"]
            self.assertEqual(
                expected["current_people"] + expected["remain_people"],
                expected["target_people"],
            )

    def test_test_split_contains_twenty_curated_records(self) -> None:
        records = build_split(
            "test",
            seed=20260712,
            curated_path=Path("data/finetune/curated_test_cases.jsonl"),
        )
        self.assertGreaterEqual(
            sum(bool(record["metadata"].get("curated")) for record in records),
            20,
        )

    def test_split_utterances_do_not_exactly_overlap(self) -> None:
        normalized: dict[str, set[str]] = {}
        for split in ("train", "val", "test"):
            records = build_split(split, seed=20260712)
            normalized[split] = {
                normalize_utterance(record["conversations"][0]["value"])
                for record in records
            }
        self.assertTrue(normalized["train"].isdisjoint(normalized["val"]))
        self.assertTrue(normalized["train"].isdisjoint(normalized["test"]))
        self.assertTrue(normalized["val"].isdisjoint(normalized["test"]))

    def test_validator_rejects_unknown_tool_and_bad_math(self) -> None:
        record = next(
            item for item in build_split("train", seed=20260712)
            if item["metadata"]["scenario"] == "group_buy_progress"
        )
        corrupted = deepcopy(record)
        call = json.loads(corrupted["conversations"][1]["value"])
        call["name"] = "unknown_tool"
        corrupted["conversations"][1]["value"] = json.dumps(call)
        corrupted["metadata"]["expected"]["remain_people"] += 1
        errors = validate_record(corrupted, "train")
        self.assertTrue(any("unknown_tool" in error for error in errors))
        self.assertTrue(any("remain_people" in error for error in errors))

    def test_validator_rejects_pii(self) -> None:
        record = deepcopy(build_split("train", seed=20260712)[0])
        record["conversations"][0]["value"] = "手机号 13800138000"
        self.assertTrue(any("PII" in error for error in validate_record(record, "train")))

    def test_checked_in_artifacts_pass_full_validation(self) -> None:
        report = validate_files(Path("data/finetune"))
        self.assertTrue(report["valid"], "\n".join(report["errors"][:20]))
        self.assertEqual(report["counts"], {"train": 800, "val": 100, "test": 100})


if __name__ == "__main__":
    unittest.main()
