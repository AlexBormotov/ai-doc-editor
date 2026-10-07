"""Command line: `ai-doc-reader edit FILE -i "..."` and `ai-doc-reader providers`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ai_doc_reader.editor import edit_document
from ai_doc_reader.llm.registry import PROVIDERS, get_provider, list_models
from ai_doc_reader.models import ChangeStatus
from ai_doc_reader.presets import PRESETS, build_instruction
from ai_doc_reader.settings import get_settings


def _edit(args: argparse.Namespace) -> int:
    s = get_settings()
    instruction = build_instruction(args.preset, args.instruction)
    provider = get_provider(args.provider or s.default_provider, args.model or s.default_model)
    src = Path(args.file)
    out_dir = Path(args.out_dir) if args.out_dir else src.parent / f"{src.stem}.ai-doc-reader"

    def progress(fraction: float, message: str) -> None:
        print(f"[{fraction:4.0%}] {message}", file=sys.stderr)

    result = edit_document(
        src, instruction, provider, out_dir, track_changes=not args.no_track, progress=progress
    )
    r = result.report
    print(f"output:  {result.output}")
    if getattr(result, "converted", None):
        print(f"converted: {result.converted}")
    print(f"report:  {result.report_html}")
    print(" ".join(f"{st.value}={r.count(st)}" for st in ChangeStatus))
    if r.violations:
        print("structure check FAILED:", *r.violations, sep="\n  ")
        return 2
    print("structure check passed")
    return 0


def _providers(_: argparse.Namespace) -> int:
    for key in PROVIDERS:
        models = ", ".join(m for m in list_models(key) if m) or "(default)"
        print(f"{key:12} {models}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-doc-reader", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("edit", help="edit a .docx, .doc or .pdf by instruction")
    e.add_argument("file")
    e.add_argument("-i", "--instruction")
    e.add_argument("-p", "--preset", choices=sorted(PRESETS))
    e.add_argument("--provider", choices=PROVIDERS)
    e.add_argument("-m", "--model")
    e.add_argument("--no-track", action="store_true", help="DOCX: apply edits without redline")
    e.add_argument("-o", "--out-dir")
    e.set_defaults(func=_edit)
    p = sub.add_parser("providers", help="list providers and their models")
    p.set_defaults(func=_providers)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
