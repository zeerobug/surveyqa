"""Output formats: terminal summary, JSON, CSV (for translators), self-contained HTML."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from surveyqa.models import Issue, Survey

FIELDS = ["row", "item_id", "lang", "severity", "check", "message", "source", "target",
          "suggestion"]


def summary(issues: list[Issue]) -> dict:
    return {
        "total": len(issues),
        "by_severity": dict(Counter(i.severity.value for i in issues)),
        "by_check": dict(Counter(i.check for i in issues).most_common()),
        "by_lang": dict(Counter(i.lang or "-" for i in issues)),
    }


def to_json(survey: Survey, issues: list[Issue], path: Path) -> None:
    payload = {
        "survey": survey.name,
        "source_lang": survey.source_lang,
        "target_langs": survey.target_langs,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary(issues),
        "issues": [i.to_dict() for i in issues],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def to_csv(issues: list[Issue], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:  # BOM so Excel opens UTF-8
        w = csv.DictWriter(fh, fieldnames=FIELDS + ["reviewer_decision", "reviewer_comment"])
        w.writeheader()
        for i in issues:
            d = i.to_dict()
            w.writerow({k: d.get(k) for k in FIELDS})


def to_terminal(survey: Survey, issues: list[Issue], max_rows: int = 40) -> str:
    s = summary(issues)
    sev = s["by_severity"]
    lines = [
        f"surveyqa: {survey.name}  ({len(survey.items)} items, "
        f"{survey.source_lang} -> {', '.join(survey.target_langs)})",
        f"  {sev.get('error', 0)} errors, {sev.get('warning', 0)} warnings, "
        f"{sev.get('info', 0)} info",
        "",
    ]
    icon = {"error": "E", "warning": "W", "info": "i"}
    for i in issues[:max_rows]:
        lines.append(f"  [{icon[i.severity.value]}] row {i.row or '-':>4}  {i.item_id or '-':<12} "
                     f"{i.lang or '-':<5} {i.check:<26} {i.message}")
    if len(issues) > max_rows:
        lines.append(f"  ... and {len(issues) - max_rows} more (see the HTML/CSV report)")
    return "\n".join(lines)


def to_html(survey: Survey, issues: list[Issue], path: Path) -> None:
    s = summary(issues)
    e = html.escape
    rows = "\n".join(
        f'<tr class="{i.severity.value}" data-lang="{e(i.lang or "")}" '
        f'data-check="{e(i.check)}">'
        f"<td>{i.row or ''}</td><td>{e(i.item_id or '')}</td><td>{e(i.lang or '')}</td>"
        f'<td><span class="badge {i.severity.value}">{i.severity.value}</span></td>'
        f"<td><code>{e(i.check)}</code></td><td>{e(i.message)}</td>"
        f'<td class="txt">{e(i.source or "")}</td><td class="txt">{e(i.target or "")}</td>'
        f'<td class="txt">{e(i.suggestion or "")}</td></tr>'
        for i in issues
    )
    langs = "".join(f'<option value="{e(lg)}">{e(lg)}</option>' for lg in survey.target_langs)
    checks = "".join(f'<option value="{e(c)}">{e(c)} ({n})</option>'
                     for c, n in s["by_check"].items())
    sev = s["by_severity"]
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>surveyqa report: {e(survey.name)}</title>
<style>
:root {{ --err:#c0392b; --warn:#b7791f; --info:#4a6fa5; --bg:#fafafa; --line:#e5e5e5; }}
body {{ font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; margin: 0;
       background: var(--bg); color: #1d1d1f; }}
header {{ padding: 24px 32px 8px; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
.meta {{ color: #666; }}
.cards {{ display: flex; gap: 12px; padding: 12px 32px; flex-wrap: wrap; }}
.card {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; padding: 10px 16px;
        min-width: 110px; }}
.card b {{ display: block; font-size: 22px; }}
.card.error b {{ color: var(--err); }} .card.warning b {{ color: var(--warn); }}
.card.info b {{ color: var(--info); }}
.filters {{ padding: 8px 32px; display: flex; gap: 8px; flex-wrap: wrap; }}
select, input {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; font: inherit; }}
.wrap {{ padding: 8px 32px 32px; overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; background: #fff; border: 1px solid var(--line); }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line);
         vertical-align: top; }}
th {{ background: #f3f3f3; position: sticky; top: 0; font-weight: 600; }}
td.txt {{ max-width: 320px; white-space: pre-wrap; }}
.badge {{ font-size: 12px; padding: 2px 8px; border-radius: 10px; color: #fff; }}
.badge.error {{ background: var(--err); }} .badge.warning {{ background: var(--warn); }}
.badge.info {{ background: var(--info); }}
code {{ font-size: 12px; }}
</style></head><body>
<header><h1>Translation QA: {e(survey.name)}</h1>
<div class="meta">{len(survey.items)} items · {e(survey.source_lang)} →
{e(", ".join(survey.target_langs))} · generated
{datetime.now().strftime("%Y-%m-%d %H:%M")} by surveyqa</div></header>
<div class="cards">
<div class="card error"><b>{sev.get("error", 0)}</b>errors</div>
<div class="card warning"><b>{sev.get("warning", 0)}</b>warnings</div>
<div class="card info"><b>{sev.get("info", 0)}</b>info</div>
</div>
<div class="filters">
<select id="sev"><option value="">All severities</option><option>error</option>
<option>warning</option><option>info</option></select>
<select id="lang"><option value="">All languages</option>{langs}</select>
<select id="check"><option value="">All checks</option>{checks}</select>
<input id="q" placeholder="Search text…">
</div>
<div class="wrap"><table><thead><tr><th>Row</th><th>Item</th><th>Lang</th><th>Severity</th>
<th>Check</th><th>Message</th><th>Source</th><th>Target</th><th>Suggestion</th></tr></thead>
<tbody id="rows">{rows}</tbody></table></div>
<script>
const f = {{sev: document.getElementById('sev'), lang: document.getElementById('lang'),
  check: document.getElementById('check'), q: document.getElementById('q')}};
function apply() {{
  const q = f.q.value.toLowerCase();
  document.querySelectorAll('#rows tr').forEach(tr => {{
    const ok = (!f.sev.value || tr.classList.contains(f.sev.value))
      && (!f.lang.value || tr.dataset.lang === f.lang.value)
      && (!f.check.value || tr.dataset.check === f.check.value)
      && (!q || tr.textContent.toLowerCase().includes(q));
    tr.style.display = ok ? '' : 'none';
  }});
}}
Object.values(f).forEach(el => el.addEventListener('input', apply));
</script></body></html>"""
    path.write_text(doc, encoding="utf-8")
