"""Cross-item consistency: glossary, do-not-translate terms, register (tú/usted, du/Sie)."""

from __future__ import annotations

import re
from collections import Counter

from surveyqa.checks import Context, segment_check, survey_check
from surveyqa.models import Issue, Severity, Survey


def _contains(text: str, term: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.IGNORECASE) is not None


@segment_check("glossary", category="consistency")
def glossary(seg, ctx: Context):
    """Glossary terms in the source must use the approved target term."""
    if not ctx.glossary or not seg.target.strip():
        return
    for entry in ctx.glossary:
        if entry.get("lang") and entry["lang"] != seg.target_lang:
            continue
        src_term, tgt_term = entry.get("source", ""), entry.get("target", "")
        if src_term and tgt_term and _contains(seg.source, src_term) \
                and not _contains(seg.target, tgt_term):
            yield Issue(
                check="glossary", severity=Severity.WARNING,
                message=f"Glossary: '{src_term}' should be translated as '{tgt_term}'",
                item_id=seg.item.id, lang=seg.target_lang, row=seg.item.row,
                source=seg.source, target=seg.target,
            )


@segment_check("do_not_translate", category="consistency")
def do_not_translate(seg, ctx: Context):
    """Protected terms (brand names, institution names, acronyms) must appear verbatim."""
    if not ctx.do_not_translate or not seg.target.strip():
        return
    for term in ctx.do_not_translate:
        if term in seg.source and term not in seg.target:
            yield Issue(
                check="do_not_translate", severity=Severity.ERROR,
                message=f"Protected term '{term}' is missing or altered in the target",
                item_id=seg.item.id, lang=seg.target_lang, row=seg.item.row,
                source=seg.source, target=seg.target,
            )


# Heuristic markers of formal vs informal address. Deliberately conservative.
REGISTER_MARKERS: dict[str, dict[str, re.Pattern]] = {
    "de": {
        "formal": re.compile(r"(?<!^)(?<![.!?]\s)\b(Sie|Ihnen|Ihr|Ihre[mnrs]?)\b"),
        "informal": re.compile(r"\b(du|dich|dir|dein|deine[mnrs]?)\b", re.IGNORECASE),
    },
    "es": {
        "formal": re.compile(r"\b(usted|ustedes)\b", re.IGNORECASE),
        "informal": re.compile(r"\b(tú|tu|tus|contigo|vosotros|vosotras)\b", re.IGNORECASE),
    },
    "fr": {
        "formal": re.compile(r"\b(vous|votre|vos)\b", re.IGNORECASE),
        "informal": re.compile(r"\b(tu|toi|ton|tes)\b", re.IGNORECASE),
    },
    "it": {
        "formal": re.compile(r"\b(Lei|Suo|Sua|Suoi)\b"),
        "informal": re.compile(r"\b(tu|tuo|tua|tuoi|ti)\b", re.IGNORECASE),
    },
}


@survey_check("register", category="consistency")
def register(survey: Survey, ctx: Context):
    """Formal and informal address are mixed within one language (e.g. tú vs usted)."""
    for lang in survey.target_langs:
        markers = REGISTER_MARKERS.get(lang.split("-")[0].lower())
        if not markers:
            continue
        hits: dict[str, list] = {"formal": [], "informal": []}
        for item in survey.items:
            text = item.text(lang)
            for reg, pattern in markers.items():
                if pattern.search(text):
                    hits[reg].append(item)
        counts = Counter({k: len(v) for k, v in hits.items()})
        if counts["formal"] and counts["informal"]:
            dominant, minority = counts.most_common()[0][0], counts.most_common()[1][0]
            for item in hits[minority]:
                yield Issue(
                    check="register", severity=Severity.WARNING,
                    message=f"Mixed register: this item uses {minority} address while most "
                            f"items ({counts[dominant]}) use {dominant} address",
                    item_id=item.id, lang=lang, row=item.row,
                    source=item.text(survey.source_lang), target=item.text(lang),
                )
