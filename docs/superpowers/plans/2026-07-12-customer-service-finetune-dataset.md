# Customer Service Fine-Tune Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and validate 1000 reproducible, privacy-safe Qwen3-8B customer-service SFT records split into 800 train, 100 validation, and 100 test examples.

**Architecture:** A deterministic standard-library Python generator builds business-valid ShareGPT records from split-specific phrase banks and scenario factories. A separate validator parses every artifact, enforces quotas, tool contracts, arithmetic invariants, privacy rules, and cross-split leakage limits. Curated test cases are versioned source inputs and merged into the generated test output.

**Tech Stack:** Python 3.12 standard library, JSONL, pytest, LLaMA-Factory ShareGPT format

## Global Constraints

- Exact split sizes: train 800, validation 100, test 100.
- Exact category totals: tool calls 550, RAG 200, clarification 100, errors 50, transfer 50, safety/casual 50.
- Exact tool totals: `group_buy_progress` 220, `group_complete` 150, `balance_usage` 180.
- Tool contracts must match the current project: `group_buy_progress(user_id, team_id)`, `group_complete(user_id, team_id)`, `balance_usage(user_id)`, `knowledge_search(query)`.
- Runtime `tool_call_id` is not fabricated in ShareGPT SFT records; tool trajectories use adjacent `function_call` and `observation` messages.
- No real PII, API keys, connection strings, or production identifiers.
- Generation must be deterministic for a fixed seed.
- Validation and test phrase families must not be copied from train phrase families.
- Test contains at least 20 version-controlled curated records.
- Curated test allocation is exact: tool calls 8 (progress 3, completion 2, balance 3), RAG 4, clarification 2, errors 2, transfer 2, safety 2.
- Cross-split normalized character 3-gram Jaccard similarity must remain below `0.92`.
- Implementation uses no external generation model and adds no runtime dependency.

---

## File Structure

- Create `scripts/finetune/generate_customer_dataset.py`: scenario factories, quotas, deterministic split generation, artifact writer.
- Create `scripts/finetune/validate_customer_dataset.py`: schema, contract, arithmetic, privacy, quota, and leakage validation.
- Create `tests/test_finetune_dataset.py`: focused unit and integration tests for generation and validation.
- Create `data/finetune/curated_test_cases.jsonl`: at least 20 hand-authored test-source records.
- Generate `data/finetune/customer_service_train.jsonl`: 800 records.
- Generate `data/finetune/customer_service_val.jsonl`: 100 records.
- Generate `data/finetune/customer_service_test.jsonl`: 100 records.
- Generate `data/finetune/dataset_info.json`: LLaMA-Factory registrations.
- Generate `data/finetune/dataset_stats.json`: scanned counts, scenario counts, hashes, and approximate text sizes.

---

### Task 1: Generator contracts and quota tests

**Files:**
- Create: `tests/test_finetune_dataset.py`
- Create: `scripts/finetune/__init__.py`
- Create: `scripts/finetune/generate_customer_dataset.py`

**Interfaces:**
- Produces: `build_split(split: str, seed: int, curated_path: Path | None = None) -> list[dict]`
- Produces: `write_outputs(root: Path, seed: int = 20260712) -> dict[str, Path]`
- Produces constants: `CATEGORY_COUNTS`, `TOOL_COUNTS`, `TOOLS_JSON`, `SYSTEM_PROMPT`

- [ ] **Step 1: Write failing quota and determinism tests**

```python
from collections import Counter
from pathlib import Path

from scripts.finetune.generate_customer_dataset import build_split


def test_split_sizes_and_category_quotas():
    expected = {
        "train": {"tool_call": 440, "rag": 160, "clarification": 80, "error": 40, "transfer": 40, "safety": 40},
        "val": {"tool_call": 55, "rag": 20, "clarification": 10, "error": 5, "transfer": 5, "safety": 5},
        "test": {"tool_call": 55, "rag": 20, "clarification": 10, "error": 5, "transfer": 5, "safety": 5},
    }
    for split, quotas in expected.items():
        records = build_split(split, seed=20260712, curated_path=None)
        assert len(records) == sum(quotas.values())
        assert Counter(r["metadata"]["category"] for r in records) == Counter(quotas)


def test_generation_is_deterministic():
    first = build_split("train", seed=20260712)
    second = build_split("train", seed=20260712)
    assert first == second
```

- [ ] **Step 2: Run the focused tests and verify import failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: FAIL because `scripts.finetune.generate_customer_dataset` does not yet expose `build_split`.

- [ ] **Step 3: Add quota constants and deterministic split skeleton**

```python
CATEGORY_COUNTS = {
    "train": {"tool_call": 440, "rag": 160, "clarification": 80, "error": 40, "transfer": 40, "safety": 40},
    "val": {"tool_call": 55, "rag": 20, "clarification": 10, "error": 5, "transfer": 5, "safety": 5},
    "test": {"tool_call": 55, "rag": 20, "clarification": 10, "error": 5, "transfer": 5, "safety": 5},
}

TOOL_COUNTS = {
    "train": {"group_buy_progress": 176, "group_complete": 120, "balance_usage": 144},
    "val": {"group_buy_progress": 22, "group_complete": 15, "balance_usage": 18},
    "test": {"group_buy_progress": 22, "group_complete": 15, "balance_usage": 18},
}


def build_split(split: str, seed: int, curated_path=None) -> list[dict]:
    if split not in CATEGORY_COUNTS:
        raise ValueError(f"unsupported split: {split}")
    records = []
    for category, count in CATEGORY_COUNTS[split].items():
        records.extend(build_category(split, category, count, seed))
    return sorted(records, key=lambda item: item["metadata"]["sample_id"])
```

`build_category` initially returns structurally valid minimal records with unique IDs; later tasks replace category bodies with complete business scenarios.

- [ ] **Step 4: Run tests and verify quota tests pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: PASS for size and deterministic-generation tests.

- [ ] **Step 5: Commit generator contract**

```bash
git add scripts/finetune tests/test_finetune_dataset.py
git commit -m "test: define fine-tune dataset quotas"
```

---

### Task 2: Business-valid scenario factories

**Files:**
- Modify: `scripts/finetune/generate_customer_dataset.py`
- Modify: `tests/test_finetune_dataset.py`

**Interfaces:**
- Consumes: `CATEGORY_COUNTS`, `TOOL_COUNTS`
- Produces: `make_progress_record`, `make_complete_record`, `make_balance_record`, `make_rag_record`, `make_clarification_record`, `make_error_record`, `make_transfer_record`, `make_safety_record`

- [ ] **Step 1: Write failing tool-contract and arithmetic tests**

```python
import json


def function_call(record):
    message = next(m for m in record["conversations"] if m["from"] == "function_call")
    return json.loads(message["value"])


def test_tool_call_counts_and_exact_arguments():
    expected = {"group_buy_progress": 220, "group_complete": 150, "balance_usage": 180}
    actual = Counter()
    for split in ("train", "val", "test"):
        for record in build_split(split, seed=20260712):
            if record["metadata"]["category"] != "tool_call":
                continue
            call = function_call(record)
            actual[call["name"]] += 1
            if call["name"] in {"group_buy_progress", "group_complete"}:
                assert set(call["arguments"]) == {"user_id", "team_id"}
            else:
                assert set(call["arguments"]) == {"user_id"}
    assert actual == Counter(expected)


def test_progress_observation_arithmetic():
    for record in build_split("train", seed=20260712):
        if record["metadata"].get("scenario") != "group_buy_progress":
            continue
        business = record["metadata"]["expected"]
        assert business["current_people"] + business["remain_people"] == business["target_people"]
```

- [ ] **Step 2: Run tests and confirm failures identify placeholder category records**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: FAIL because tool-call messages and expected business metadata are not implemented.

- [ ] **Step 3: Implement exact tool schemas and scenario factories**

Implement each factory with split-specific phrase banks and deterministic values. Tool-call records always use:

```python
{
    "from": "function_call",
    "value": json.dumps(
        {"name": tool_name, "arguments": arguments},
        ensure_ascii=False,
        separators=(",", ":"),
    ),
}
```

Progress metadata stores `current_people`, `target_people`, `remain_people`, and `expire_at`; balance metadata stores `total_quota`, `used`, and `remaining`; completion metadata stores `is_complete` and `complete_at`. Factory code derives response values from the same metadata object used to build observations.

- [ ] **Step 4: Run all dataset tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: PASS for quotas, exact arguments, and arithmetic invariants.

- [ ] **Step 5: Commit business factories**

```bash
git add scripts/finetune/generate_customer_dataset.py tests/test_finetune_dataset.py
git commit -m "feat: generate business-valid agent samples"
```

---

### Task 3: Curated test cases and cross-split leakage protection

**Files:**
- Create: `data/finetune/curated_test_cases.jsonl`
- Modify: `scripts/finetune/generate_customer_dataset.py`
- Modify: `tests/test_finetune_dataset.py`

**Interfaces:**
- Produces: `load_curated_test_cases(path: Path) -> list[dict]`
- Produces: `normalize_utterance(text: str) -> str`
- Produces: `char_ngrams(text: str, n: int = 3) -> set[str]`

- [ ] **Step 1: Write failing curated-count and leakage tests**

```python
def test_test_split_contains_curated_records():
    path = Path("data/finetune/curated_test_cases.jsonl")
    records = build_split("test", seed=20260712, curated_path=path)
    assert sum(r["metadata"].get("curated", False) for r in records) >= 20


def test_split_utterances_do_not_exactly_overlap():
    normalized = {}
    for split in ("train", "val", "test"):
        records = build_split(split, seed=20260712, curated_path=Path("data/finetune/curated_test_cases.jsonl"))
        normalized[split] = {
            normalize_utterance(r["conversations"][0]["value"])
            for r in records
        }
    assert normalized["train"].isdisjoint(normalized["val"])
    assert normalized["train"].isdisjoint(normalized["test"])
    assert normalized["val"].isdisjoint(normalized["test"])
```

- [ ] **Step 2: Run tests and verify curated file is missing**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: FAIL because curated records and normalization helpers do not exist.

- [ ] **Step 3: Add at least 20 manually authored test records**

Curated records cover unseen colloquial expressions, multi-intent requests, missing identifiers, attempted cross-user lookup, prompt injection, tool timeout, RAG miss, and transfer-to-human language. Each record contains `metadata.curated=true`, a unique `test-curated-*` ID, and a scenario-valid conversation.

Use this exact curated allocation: tool calls 8 (progress 3, completion 2, balance 3), RAG 4, clarification 2, errors 2, transfer 2, and safety 2.

- [ ] **Step 4: Merge curated records without changing the 100-record test quota**

`build_split("test", ...)` reserves 20 test slots for curated records and generates only the remaining per-category counts. Curated-category counts are subtracted from the matching test quotas, and the generator raises if any curated category exceeds its quota.

- [ ] **Step 5: Run tests and verify curated and leakage checks pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: PASS.

- [ ] **Step 6: Commit curated test inputs**

```bash
git add data/finetune/curated_test_cases.jsonl scripts/finetune/generate_customer_dataset.py tests/test_finetune_dataset.py
git commit -m "feat: add curated customer-service test cases"
```

---

### Task 4: Standalone validator

**Files:**
- Create: `scripts/finetune/validate_customer_dataset.py`
- Modify: `tests/test_finetune_dataset.py`

**Interfaces:**
- Produces: `validate_record(record: dict, split: str) -> list[str]`
- Produces: `validate_files(root: Path) -> dict`
- CLI exits 0 on success and non-zero with line-specific errors on failure.

- [ ] **Step 1: Write failing corruption tests**

```python
from copy import deepcopy
from scripts.finetune.validate_customer_dataset import validate_record


def test_validator_rejects_unknown_tool_and_bad_math():
    record = next(
        r for r in build_split("train", seed=20260712)
        if r["metadata"].get("scenario") == "group_buy_progress"
    )
    corrupted = deepcopy(record)
    call = json.loads(corrupted["conversations"][1]["value"])
    call["name"] = "unknown_tool"
    corrupted["conversations"][1]["value"] = json.dumps(call)
    corrupted["metadata"]["expected"]["remain_people"] += 1
    errors = validate_record(corrupted, "train")
    assert any("unknown_tool" in error for error in errors)
    assert any("remain_people" in error for error in errors)


def test_validator_rejects_pii():
    record = deepcopy(build_split("train", seed=20260712)[0])
    record["conversations"][0]["value"] = "手机号13800138000"
    assert any("PII" in error for error in validate_record(record, "train"))
```

- [ ] **Step 2: Run tests and verify validator import failure**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: FAIL because the validator does not exist.

- [ ] **Step 3: Implement record and aggregate validation**

The validator checks JSON shape, allowed roles, tool adjacency, exact argument sets, scenario arithmetic, IDs, privacy regexes, split prefixes, quotas, exact duplicates, normalized duplicates, cross-split 3-gram Jaccard similarity `>= 0.92`, dataset registration, and stats consistency. It reports `file:line: message` for record errors.

- [ ] **Step 4: Run unit tests and confirm corrupted records are rejected**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py -q`

Expected: PASS.

- [ ] **Step 5: Commit validator**

```bash
git add scripts/finetune/validate_customer_dataset.py tests/test_finetune_dataset.py
git commit -m "feat: validate fine-tune dataset integrity"
```

---

### Task 5: Generate final artifacts and verify end to end

**Files:**
- Generate: `data/finetune/customer_service_train.jsonl`
- Generate: `data/finetune/customer_service_val.jsonl`
- Generate: `data/finetune/customer_service_test.jsonl`
- Generate: `data/finetune/dataset_info.json`
- Generate: `data/finetune/dataset_stats.json`
- Modify: `tests/test_finetune_dataset.py`

**Interfaces:**
- Consumes: `write_outputs`, `validate_files`
- Produces: reproducible static training artifacts accepted by LLaMA-Factory.

- [ ] **Step 1: Add end-to-end artifact test**

```python
def test_checked_in_artifacts_pass_full_validation():
    from scripts.finetune.validate_customer_dataset import validate_files
    report = validate_files(Path("data/finetune"))
    assert report["valid"] is True
    assert report["counts"] == {"train": 800, "val": 100, "test": 100}
```

- [ ] **Step 2: Run the test and verify generated files are missing**

Run: `.venv/Scripts/python.exe -m pytest tests/test_finetune_dataset.py::test_checked_in_artifacts_pass_full_validation -q`

Expected: FAIL with missing artifact paths.

- [ ] **Step 3: Generate all artifacts**

Run: `.venv/Scripts/python.exe scripts/finetune/generate_customer_dataset.py --output-dir data/finetune --seed 20260712`

Expected: reports `train=800 val=100 test=100` and writes the five generated artifacts without changing `curated_test_cases.jsonl`.

`dataset_info.json` contains three LLaMA-Factory entries named `customer_service_train`, `customer_service_val`, and `customer_service_test`, each using `formatting=sharegpt` and mapping `messages=conversations`, `system=system`, and `tools=tools`. `dataset_stats.json` contains seed, split counts, category counts, tool counts, curated count, approximate character totals, and SHA-256 per JSONL artifact.

- [ ] **Step 4: Run standalone validation**

Run: `.venv/Scripts/python.exe scripts/finetune/validate_customer_dataset.py --data-dir data/finetune`

Expected: exit 0 and print category totals, tool totals, curated count, duplicate count 0, leakage count 0, and privacy violations 0.

- [ ] **Step 5: Run all project tests**

Run: `.venv/Scripts/python.exe -m pytest -q`

Expected: all tests pass, including the dataset suite.

- [ ] **Step 6: Regenerate into a temporary directory and compare hashes**

Run: `.venv/Scripts/python.exe scripts/finetune/generate_customer_dataset.py --output-dir .tmp/finetune-repro --seed 20260712`

Compare SHA-256 for train, validation, test, dataset info, and stats files against `data/finetune`. Expected: all hashes match.

- [ ] **Step 7: Commit generated artifacts**

```bash
git add data/finetune scripts/finetune tests/test_finetune_dataset.py
git commit -m "feat: add customer-service fine-tune dataset"
```
