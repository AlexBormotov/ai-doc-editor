"""Measure real models on evals/tasks.yaml.

    uv run poe eval-models --provider ollama --model qwen3.5:9b [--provider ... --model ...]

Per model: task success (deterministic checks on the output text), structure check, valid-JSON
rate (batches not rejected as invalid_response), invented segment IDs, and wall time. Results go
to evals/results/<provider>_<model>.json and the table in evals/results/summary.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import pymupdf
import yaml

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))

from ai_doc_reader.docx.reader import read_docx  # noqa: E402
from ai_doc_reader.editor import edit_document  # noqa: E402
from ai_doc_reader.llm.base import LLMError  # noqa: E402
from ai_doc_reader.llm.registry import get_provider  # noqa: E402
from ai_doc_reader.models import ChangeStatus  # noqa: E402
from ai_doc_reader.presets import build_instruction  # noqa: E402

RESULTS = ROOT / "results"
LANDED = (ChangeStatus.APPLIED, ChangeStatus.SHORTENED, ChangeStatus.SHRUNK)


def output_text(path: Path) -> str:
    if path.suffix == ".pdf":
        with pymupdf.open(str(path)) as d:
            return " ".join(" ".join(p.get_text().split()) for p in d)
    return " ".join(s.text for s in read_docx(path).segments)


def run_checks(text: str, changed: int, checks: dict) -> list[str]:
    failed = []
    for s in checks.get("absent", []):
        if s in text:
            failed.append(f"still contains {s!r}")
    for s in checks.get("present", []):
        if s not in text:
            failed.append(f"missing {s!r}")
    for rx in checks.get("absent_regex", []):
        if re.search(rx, text):
            failed.append(f"still matches /{rx}/")
    if "max_cyrillic_ratio" in checks:
        letters = [c for c in text if c.isalpha()]
        ratio = sum("а" <= c.lower() <= "я" or c in "ёЁ" for c in letters) / max(1, len(letters))
        if ratio > checks["max_cyrillic_ratio"]:
            failed.append(f"cyrillic ratio {ratio:.0%}")
    if "max_changed" in checks and changed > checks["max_changed"]:
        failed.append(f"changed {changed} segments (> {checks['max_changed']}: over-editing)")
    return failed


def eval_model(provider_key: str, model: str, tasks: list[dict]) -> dict:
    provider = get_provider(provider_key, model)
    rows = []
    for task in tasks:
        instruction = build_instruction(task.get("preset"), task.get("instruction"))
        with tempfile.TemporaryDirectory() as tmp:
            try:
                result = edit_document(
                    ROOT / "fixtures" / task["fixture"], instruction, provider, Path(tmp)
                )
            except LLMError as e:
                rows.append({"task": task["id"], "success": False, "error": str(e)[:300]})
                print(f"  {task['id']:22} ERROR {e}")
                continue
            r = result.report
            changed = sum(r.count(s) for s in LANDED)
            failed = run_checks(output_text(result.output), changed, task["checks"])
            invalid = [c for c in r.changes if c.reason == "invalid_response"]
            row = {
                "task": task["id"],
                "success": not failed and not r.violations,
                "failed_checks": failed,
                "structure_ok": not r.violations,
                "violations": r.violations[:3],
                "changed": changed,
                "invalid_response_segments": len(invalid),
                "invented_ids": sum(1 for c in r.changes if c.reason == "unknown_id"),
                "does_not_fit": sum(1 for c in r.changes if c.reason == "does_not_fit"),
                "seconds": round(r.duration_s, 1),
            }
            rows.append(row)
            mark = "PASS" if row["success"] else "FAIL"
            why = "; ".join(failed + r.violations[:2])
            print(f"  {task['id']:22} {mark} {row['seconds']:6.1f}s {why}")
    ok = [r for r in rows if "error" not in r]
    summary = {
        "provider": provider_key,
        "model": model,
        "tasks": len(rows),
        "passed": sum(r["success"] for r in rows),
        "structure_ok": sum(r.get("structure_ok", False) for r in rows),
        "invalid_json_tasks": sum(1 for r in ok if r["invalid_response_segments"]),
        "invented_ids": sum(r["invented_ids"] for r in ok),
        "total_seconds": round(sum(r.get("seconds", 0) for r in ok), 1),
        "rows": rows,
    }
    return summary


def write_summary() -> None:
    lines = [
        "| Provider | Model | Tasks passed | Structure check | Tasks with invalid JSON "
        "| Invented IDs | Total time |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in sorted(RESULTS.glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        lines.append(
            f"| {s['provider']} | `{s['model'] or 'default'}` | {s['passed']}/{s['tasks']} "
            f"| {s['structure_ok']}/{s['tasks']} | {s['invalid_json_tasks']} "
            f"| {s['invented_ids']} | {s['total_seconds']:.0f} s |"
        )
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", action="append", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--task", action="append", help="run only these task ids")
    args = parser.parse_args()
    if len(args.provider) != len(args.model):
        parser.error("give one --model per --provider")
    tasks = yaml.safe_load((ROOT / "tasks.yaml").read_text(encoding="utf-8"))
    if args.task:
        tasks = [t for t in tasks if t["id"] in args.task]
    RESULTS.mkdir(exist_ok=True)
    for key, model in zip(args.provider, args.model, strict=True):
        print(f"{key} / {model or 'default'}")
        summary = eval_model(key, model, tasks)
        name = re.sub(r"[^\w.-]+", "_", f"{key}_{model or 'default'}")
        (RESULTS / f"{name}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"  -> {summary['passed']}/{summary['tasks']} passed")
    write_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
