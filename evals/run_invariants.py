"""Deterministic eval: every fixture through the full pipeline with a scripted provider.

No model is involved, so the result depends only on the readers, writers and invariant checks.
Exit code 0 when every run applies at least one edit and the structure check passes.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "src"))

from ai_doc_editor.editor import edit_document  # noqa: E402
from ai_doc_editor.llm.scripted import ScriptedProvider  # noqa: E402
from ai_doc_editor.models import ChangeStatus  # noqa: E402
from ai_doc_editor.soffice import find_soffice  # noqa: E402

RULES = [
    ("Acme Corp", "Contoso Ltd"),
    ("Acme", "Contoso"),
    ("recieve", "receive"),
    ("beleive", "believe"),
    ("adress", "address"),
    ("указаные", "указанные"),
    ("Иванов[а-яА-Я. ]*?(?=,)", "[ФИО]"),
    (r"\+7 \d{3} \d{3}-\d{2}-\d{2}", "[ТЕЛЕФОН]"),
]


def main() -> int:
    fixtures = sorted((ROOT / "fixtures").glob("*.*"))
    if find_soffice() is None:
        fixtures = [f for f in fixtures if f.suffix != ".doc"]
    failures = 0
    print(f"{'fixture':24} {'mode':9} {'applied':>7} {'other':>6}  result")
    with tempfile.TemporaryDirectory() as tmp:
        for f in fixtures:
            for track in [True, False] if f.suffix in (".docx", ".doc") else [None]:
                mode = {True: "tracked", False: "direct", None: "in-place"}[track]
                out = Path(tmp) / f"{f.stem}-{mode}"
                r = edit_document(
                    f, "scripted", ScriptedProvider(RULES), out, track_changes=bool(track)
                ).report
                landed = sum(
                    r.count(s)
                    for s in (ChangeStatus.APPLIED, ChangeStatus.SHORTENED, ChangeStatus.SHRUNK)
                )
                ok = landed > 0 and not r.violations
                failures += not ok
                other = len(r.changes) - landed
                print(f"{f.name:24} {mode:9} {landed:7} {other:6}  {'PASS' if ok else 'FAIL'}")
                for v in r.violations:
                    print(f"    {v}")
    print(f"\n{'all passed' if not failures else f'{failures} failed'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
