"""Change report as JSON and as a self-contained HTML page (AC-7)."""

from __future__ import annotations

import html
from difflib import SequenceMatcher
from pathlib import Path

from ai_doc_editor.docx.writer import _TOKEN
from ai_doc_editor.models import ChangeReport, ChangeStatus

_COLORS = {
    ChangeStatus.APPLIED: "#1a7f37",
    ChangeStatus.SHORTENED: "#0969da",
    ChangeStatus.SHRUNK: "#9a6700",
    ChangeStatus.REJECTED: "#cf222e",
    ChangeStatus.SKIPPED: "#6e7781",
}


def word_diff_html(old: str, new: str) -> str:
    a, b = _TOKEN.findall(old), _TOKEN.findall(new)
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("delete", "replace"):
            out.append(f"<del>{html.escape(''.join(a[i1:i2]))}</del>")
        if tag in ("insert", "replace"):
            out.append(f"<ins>{html.escape(''.join(b[j1:j2]))}</ins>")
        if tag == "equal":
            out.append(html.escape("".join(a[i1:i2])))
    return "".join(out)


def write_json(report: ChangeReport, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")


def write_html(report: ChangeReport, path: Path) -> None:
    rows = []
    for c in report.changes:
        diff = word_diff_html(c.old_text, c.new_text) if c.new_text is not None else ""
        if c.status in (ChangeStatus.REJECTED, ChangeStatus.SKIPPED) and c.new_text:
            proposed = html.escape(c.new_text)
            diff = f"{html.escape(c.old_text)}<div class=prop>proposed: {proposed}</div>"
        elif not diff:
            diff = html.escape(c.old_text)
        notes = ", ".join([c.reason or "", *c.notes]).strip(", ")
        rows.append(
            f"<tr><td><code>{html.escape(c.id)}</code></td>"
            f"<td><span class=st style='background:{_COLORS[c.status]}'>"
            f"{c.status.value}</span></td>"
            f"<td>{diff}</td><td class=notes>{html.escape(notes)}</td></tr>"
        )
    verified = (
        "<p class=ok>Structure check passed: untouched content is unchanged.</p>"
        if not report.violations
        else "<p class=bad>Structure check found problems:</p><ul>"
        + "".join(f"<li>{html.escape(v)}</li>" for v in report.violations)
        + "</ul>"
    )
    conv = ""
    if report.conversion:
        g = report.conversion
        if g["passed"]:
            conv = f"<p class=ok>Converted to {g['target'].upper()}: layout check passed.</p>"
        else:
            items = "".join(f"<li>{html.escape(x)}</li>" for x in g["failures"])
            conv = (
                f"<p class=bad>Converted to {g['target'].upper()}: layout NOT verified "
                f"({html.escape(g['file'])}).</p><ul>{items}</ul>"
            )
        if g.get("note"):
            conv += f"<p class=notes>{html.escape(g['note'])}</p>"
    if report.scope:
        conv = (
            f"<p>Instruction applied to {len(report.scope)} segment(s) chosen by the model: "
            f"{html.escape(', '.join(report.scope))}</p>" + conv
        )
    counts = " · ".join(f"{s.value}: {report.count(s)}" for s in ChangeStatus if report.count(s))
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Change report</title><style>
body{{font:14px/1.5 system-ui,sans-serif;margin:24px;color:#1f2328;background:#fff}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #d0d7de;padding:6px 8px;
vertical-align:top;text-align:left}}del{{background:#ffebe9;color:#82071e}}
ins{{background:#dafbe1;color:#116329;text-decoration:none}}.st{{color:#fff;border-radius:10px;
padding:1px 8px;font-size:12px}}.notes{{color:#57606a;font-size:12px}}.prop{{color:#57606a}}
.ok{{color:#1a7f37}}.bad{{color:#cf222e}}code{{font-size:12px}}
</style></head><body>
<h1>Change report</h1>
<p><b>{html.escape(report.source_name)}</b> &rarr;
<b>{html.escape(report.output_name or "")}</b><br>
Provider: {html.escape(report.provider)} / {html.escape(report.model)} ·
{report.segments_sent} of {report.segments_total} segments sent · {report.duration_s:.1f} s<br>
Instruction: {html.escape(report.instruction)}</p>
<p>{counts or "No changes."}</p>{verified}{conv}
<table><tr><th>Segment</th><th>Status</th><th>Change</th><th>Notes</th></tr>
{"".join(rows)}</table></body></html>"""
    path.write_text(page, encoding="utf-8")
