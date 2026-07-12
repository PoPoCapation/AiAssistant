"""Validate generated customer-service fine-tuning artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.finetune.generate_customer_dataset import (
    CATEGORY_COUNTS,
    TOOL_COUNTS,
    char_ngrams,
    normalize_utterance,
)


FILE_NAMES = {
    "train": "customer_service_train.jsonl",
    "val": "customer_service_val.jsonl",
    "test": "customer_service_test.jsonl",
}
TOOL_ARGUMENTS = {
    "group_buy_progress": {"user_id", "team_id"},
    "group_complete": {"user_id", "team_id"},
    "balance_usage": {"user_id"},
    "knowledge_search": {"query"},
}
ALLOWED_ROLES = {"human", "gpt", "function_call", "observation"}
PII_PATTERNS = {
    "phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "id_card": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "secret": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|(?:mysql|postgres(?:ql)?|redis)://\S+)"),
}
CURATED_CATEGORY_COUNTS = Counter(
    {"tool_call": 8, "rag": 4, "clarification": 2, "error": 2, "transfer": 2, "safety": 2}
)
CURATED_TOOL_COUNTS = Counter({"group_buy_progress": 3, "group_complete": 2, "balance_usage": 3})


def _json_object(value: Any, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        result = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        errors.append(f"{label} must be valid JSON")
        return None
    if not isinstance(result, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return result


def validate_record(record: dict, split: str) -> list[str]:
    """Return all validation errors for one ShareGPT record."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record must be an object"]

    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        return ["metadata must be an object"]
    sample_id = metadata.get("sample_id", "<missing-id>")
    if metadata.get("split") != split:
        errors.append(f"{sample_id}: metadata split must be {split}")
    if not isinstance(sample_id, str) or not sample_id.startswith(f"{split}-"):
        errors.append(f"{sample_id}: sample_id must start with {split}-")
    if metadata.get("category") not in CATEGORY_COUNTS.get(split, {}):
        errors.append(f"{sample_id}: invalid category {metadata.get('category')!r}")

    if not isinstance(record.get("system"), str) or not record["system"].strip():
        errors.append(f"{sample_id}: system prompt is missing")
    try:
        parsed_tools = json.loads(record.get("tools", ""))
        if not isinstance(parsed_tools, list):
            errors.append(f"{sample_id}: tools must be a JSON array")
        else:
            definitions = {item.get("name"): item for item in parsed_tools if isinstance(item, dict)}
            if set(definitions) != set(TOOL_ARGUMENTS):
                errors.append(f"{sample_id}: tools must define the four approved tools")
            for tool_name, argument_names in TOOL_ARGUMENTS.items():
                parameters = definitions.get(tool_name, {}).get("parameters", {})
                if set(parameters.get("properties", {})) != argument_names or set(parameters.get("required", [])) != argument_names:
                    errors.append(f"{sample_id}: invalid schema for {tool_name}")
    except (TypeError, json.JSONDecodeError):
        errors.append(f"{sample_id}: tools must be valid JSON")

    conversations = record.get("conversations")
    if not isinstance(conversations, list) or not conversations:
        return errors + [f"{sample_id}: conversations must be a non-empty list"]
    roles: list[str] = []
    for index, message in enumerate(conversations):
        if not isinstance(message, dict):
            errors.append(f"{sample_id}: message {index} must be an object")
            continue
        role = message.get("from")
        roles.append(role)
        if role not in ALLOWED_ROLES:
            errors.append(f"{sample_id}: invalid role {role!r}")
        value = message.get("value")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{sample_id}: message {index} has empty value")
        else:
            for pii_name, pattern in PII_PATTERNS.items():
                if pattern.search(value):
                    errors.append(f"{sample_id}: PII detected ({pii_name})")

    if roles and (roles[0] != "human" or roles[-1] != "gpt"):
        errors.append(f"{sample_id}: conversation must start with human and end with gpt")
    function_positions = [index for index, role in enumerate(roles) if role == "function_call"]
    observation_positions = [index for index, role in enumerate(roles) if role == "observation"]
    if bool(function_positions) != bool(observation_positions):
        errors.append(f"{sample_id}: function_call and observation must be paired")
    for position in function_positions:
        if position + 1 >= len(roles) or roles[position + 1] != "observation":
            errors.append(f"{sample_id}: observation must immediately follow function_call")
            continue
        call = _json_object(conversations[position].get("value"), f"{sample_id}: function_call", errors)
        if call is None:
            continue
        tool_name = call.get("name")
        arguments = call.get("arguments")
        if tool_name not in TOOL_ARGUMENTS:
            errors.append(f"{sample_id}: unknown_tool {tool_name!r}")
        elif not isinstance(arguments, dict) or set(arguments) != TOOL_ARGUMENTS[tool_name]:
            errors.append(f"{sample_id}: {tool_name} arguments must be {sorted(TOOL_ARGUMENTS[tool_name])}")

    category = metadata.get("category")
    scenario = metadata.get("scenario")
    if category == "tool_call":
        if len(function_positions) != 1:
            errors.append(f"{sample_id}: tool_call category requires one function_call")
        elif scenario in TOOL_ARGUMENTS:
            call = _json_object(conversations[function_positions[0]].get("value"), f"{sample_id}: function_call", [])
            if call and call.get("name") != scenario:
                errors.append(f"{sample_id}: scenario tool does not match function_call")
    if category == "clarification" and function_positions:
        errors.append(f"{sample_id}: clarification must not call a tool")

    expected = metadata.get("expected", {})
    if scenario == "group_buy_progress" and isinstance(expected, dict):
        values = [expected.get(key) for key in ("current_people", "remain_people", "target_people")]
        if not all(isinstance(value, int) for value in values) or values[0] + values[1] != values[2]:
            errors.append(f"{sample_id}: remain_people arithmetic is inconsistent")
    if scenario == "balance_usage" and isinstance(expected, dict):
        key_sets = (("total_quota", "used", "remaining"), ("total_balance", "used_balance", "remaining_balance"))
        available = next((keys for keys in key_sets if all(key in expected for key in keys)), None)
        if available and expected[available[0]] - expected[available[1]] != expected[available[2]]:
            errors.append(f"{sample_id}: balance arithmetic is inconsistent")
    return errors


def _read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    records: list[dict] = []
    errors: list[str] = []
    if not path.exists():
        return records, [f"{path}: missing file"]
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("record is not an object")
            records.append(value)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{path}:{line_number}: {exc}")
    return records, errors


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_files(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    records_by_split: dict[str, list[dict]] = {}
    ids: set[str] = set()
    counts: dict[str, int] = {}
    category_report: dict[str, dict[str, int]] = {}
    tool_report: dict[str, dict[str, int]] = {}

    for split, file_name in FILE_NAMES.items():
        path = root / file_name
        records, read_errors = _read_jsonl(path)
        errors.extend(read_errors)
        records_by_split[split] = records
        counts[split] = len(records)
        if len(records) != sum(CATEGORY_COUNTS[split].values()):
            errors.append(f"{path}: expected {sum(CATEGORY_COUNTS[split].values())} records, got {len(records)}")
        categories = Counter(record.get("metadata", {}).get("category") for record in records)
        category_report[split] = dict(sorted(categories.items()))
        if categories != Counter(CATEGORY_COUNTS[split]):
            errors.append(f"{path}: category quotas do not match")
        tools = Counter(
            record.get("metadata", {}).get("scenario")
            for record in records
            if record.get("metadata", {}).get("category") == "tool_call"
        )
        tool_report[split] = dict(sorted(tools.items()))
        if tools != Counter(TOOL_COUNTS[split]):
            errors.append(f"{path}: tool quotas do not match")
        for line_number, record in enumerate(records, start=1):
            for message in validate_record(record, split):
                errors.append(f"{path}:{line_number}: {message}")
            sample_id = record.get("metadata", {}).get("sample_id")
            if sample_id in ids:
                errors.append(f"{path}:{line_number}: duplicate sample_id {sample_id}")
            ids.add(sample_id)

    curated_count = sum(
        bool(record.get("metadata", {}).get("curated"))
        for record in records_by_split.get("test", [])
    )
    if curated_count < 20:
        errors.append(f"test set requires at least 20 curated records, got {curated_count}")
    curated_records = [
        record for record in records_by_split.get("test", [])
        if record.get("metadata", {}).get("curated")
    ]
    curated_categories = Counter(record["metadata"].get("category") for record in curated_records)
    curated_tools = Counter(
        record["metadata"].get("scenario")
        for record in curated_records
        if record["metadata"].get("category") == "tool_call"
    )
    if curated_categories != CURATED_CATEGORY_COUNTS:
        errors.append("curated category allocation does not match the approved 20-case plan")
    if curated_tools != CURATED_TOOL_COUNTS:
        errors.append("curated tool allocation does not match the approved 8-case plan")

    utterances: dict[str, list[tuple[str, set[str]]]] = {}
    for split, records in records_by_split.items():
        utterances[split] = [
            (normalize_utterance(record["conversations"][0]["value"]), char_ngrams(record["conversations"][0]["value"]))
            for record in records if record.get("conversations")
        ]
    leakage_count = 0
    split_pairs = (("train", "val"), ("train", "test"), ("val", "test"))
    for left, right in split_pairs:
        for left_text, left_grams in utterances.get(left, []):
            for right_text, right_grams in utterances.get(right, []):
                union = left_grams | right_grams
                similarity = len(left_grams & right_grams) / len(union) if union else float(left_text == right_text)
                if similarity >= 0.92:
                    leakage_count += 1
                    errors.append(f"cross-split leakage {left}/{right}: {left_text!r} vs {right_text!r} ({similarity:.3f})")

    info_path = root / "dataset_info.json"
    if not info_path.exists():
        errors.append(f"{info_path}: missing file")
    else:
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            for split, file_name in FILE_NAMES.items():
                entry = info.get(f"customer_service_{split}", {})
                if entry.get("file_name") != file_name or entry.get("formatting") != "sharegpt":
                    errors.append(f"{info_path}: invalid customer_service_{split} registration")
                expected_columns = {"messages": "conversations", "system": "system", "tools": "tools"}
                if entry.get("columns") != expected_columns:
                    errors.append(f"{info_path}: invalid columns for customer_service_{split}")
        except json.JSONDecodeError as exc:
            errors.append(f"{info_path}: {exc}")

    stats_path = root / "dataset_stats.json"
    if not stats_path.exists():
        errors.append(f"{stats_path}: missing file")
    else:
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
            if stats.get("counts") != counts:
                errors.append(f"{stats_path}: counts do not match scanned files")
            if stats.get("categories") != category_report:
                errors.append(f"{stats_path}: categories do not match scanned files")
            if stats.get("tools") != tool_report:
                errors.append(f"{stats_path}: tools do not match scanned files")
            if stats.get("curated_count") != curated_count:
                errors.append(f"{stats_path}: curated_count does not match scanned files")
            for split, file_name in FILE_NAMES.items():
                path = root / file_name
                if path.exists() and stats.get("sha256", {}).get(split) != _sha256(path):
                    errors.append(f"{stats_path}: sha256 mismatch for {split}")
        except json.JSONDecodeError as exc:
            errors.append(f"{stats_path}: {exc}")

    return {
        "valid": not errors,
        "errors": errors,
        "counts": counts,
        "categories": category_report,
        "tools": tool_report,
        "curated_count": curated_count,
        "leakage_count": leakage_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/finetune"))
    args = parser.parse_args()
    report = validate_files(args.data_dir)
    if report["valid"]:
        print(json.dumps({key: value for key, value in report.items() if key != "errors"}, ensure_ascii=False, indent=2))
        return 0
    for error in report["errors"]:
        print(error)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
