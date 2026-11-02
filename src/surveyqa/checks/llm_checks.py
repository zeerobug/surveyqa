"""LLM-backed checks for things regexes can't see: meaning drift and scale equivalence.

Only run when an LLM is configured (`--llm MODEL`). Every finding is returned as a
WARNING at most unless the model is confident; humans adjudicate (the 'A' in TRAPD).
"""

from __future__ import annotations

import json

from surveyqa.checks import Context, segment_check, survey_check
from surveyqa.models import Issue, Role, Severity, Survey

SYSTEM = (
    "You are a senior survey-translation reviewer following the TRAPD methodology and the "
    "Cross-Cultural Survey Guidelines. You compare a source questionnaire item with its "
    "translation and report only problems that could change how respondents understand or "
    "answer the item. Do not report style preferences. Reply with JSON only."
)

DRIFT_PROMPT = """Source language: {src_lang}
Target language: {tgt_lang}
Item role: {role}

SOURCE:
{source}

TRANSLATION:
{target}

Check for: omitted or added content, changed negation, changed quantifiers or frequency words
(always/often/never), changed intensity, changed time reference, a question that became
double-barreled or leading, wrong subject, mistranslated key terms, and culturally
inappropriate content.

Return JSON: {{"issues": [{{"type": "<short_snake_case>", "severity": "error|warning|info",
"explanation": "<one sentence, in English>", "suggestion": "<corrected translation or null>"}}]}}
Return {{"issues": []}} if the translation is faithful."""

SCALE_PROMPT = """Source language: {src_lang}
Target language: {tgt_lang}
An answer scale, in display order. Each line: position | source label | translated label

{rows}

Check that the translated scale keeps the same number of points, the same order and polarity,
roughly equal intensity steps, a symmetric structure if the source is symmetric, and the same
meaning for the midpoint and any "don't know" option.

Return JSON: {{"issues": [{{"position": <int or null>, "severity": "error|warning|info",
"explanation": "<one sentence, in English>", "suggestion": "<better label or null>"}}]}}
Return {{"issues": []}} if the scale is equivalent."""


def _sev(value: str | None) -> Severity:
    try:
        return Severity((value or "warning").lower())
    except ValueError:
        return Severity.WARNING


@segment_check("meaning_drift", category="meaning", uses_llm=True)
def meaning_drift(seg, ctx: Context):
    """LLM review of source vs target for meaning changes (negation, quantifiers, omissions)."""
    if ctx.llm is None or not seg.source.strip() or not seg.target.strip():
        return
    if seg.item.role is Role.OPTION:
        return  # options are reviewed as a whole scale below
    data = ctx.llm.complete_json(SYSTEM, DRIFT_PROMPT.format(
        src_lang=seg.source_lang, tgt_lang=seg.target_lang, role=seg.item.role.value,
        source=seg.source, target=seg.target,
    ))
    for f in (data.get("issues", []) if isinstance(data, dict) else []):
        yield Issue(
            check="meaning_drift", severity=_sev(f.get("severity")),
            message=f"[{f.get('type', 'meaning')}] {f.get('explanation', '')}".strip(),
            suggestion=f.get("suggestion"), item_id=seg.item.id, lang=seg.target_lang,
            source=seg.source, target=seg.target, row=seg.item.row,
        )


@survey_check("scale_equivalence", category="scale", uses_llm=True)
def scale_equivalence(survey: Survey, ctx: Context):
    """LLM review of each translated scale for order, polarity and intensity equivalence."""
    if ctx.llm is None:
        return
    for scale in survey.scales():
        items = scale.ordered()
        for lang in survey.target_langs:
            if not all(i.text(lang).strip() for i in items):
                continue  # incomplete scales are reported by scale_length / missing_translation
            rows = "\n".join(
                f"{n} | {i.text(survey.source_lang)} | {i.text(lang)}"
                for n, i in enumerate(items, start=1)
            )
            data = ctx.llm.complete_json(SYSTEM, SCALE_PROMPT.format(
                src_lang=survey.source_lang, tgt_lang=lang, rows=rows))
            for f in (data.get("issues", []) if isinstance(data, dict) else []):
                pos = f.get("position")
                item = items[pos - 1] if isinstance(pos, int) and 1 <= pos <= len(items) else None
                yield Issue(
                    check="scale_equivalence", severity=_sev(f.get("severity")),
                    message=f"Scale '{scale.id}': {f.get('explanation', '')}",
                    suggestion=f.get("suggestion"), lang=lang,
                    item_id=item.id if item else scale.id,
                    row=(item or items[0]).row,
                    source=item.text(survey.source_lang) if item else None,
                    target=item.text(lang) if item else None,
                    extra={"scale": json.loads(json.dumps(rows))},
                )
