"""Deterministic, per-segment checks. Fast, free and exact."""

from __future__ import annotations

import re
from collections import Counter

from surveyqa.checks import Context, segment_check
from surveyqa.models import Issue, Role, Segment, Severity

# --- helpers -----------------------------------------------------------------------------

# Placeholder / piping syntaxes seen in survey tools:
#   {name} {{name}} {TOKEN:FIRSTNAME} (LimeSurvey EM)   [Q3] (piping)   %s %1$s %(name)s
#   ${var} (XLSForm)   <<var>>
PLACEHOLDER_PATTERNS = [
    r"\{\{[^{}]+\}\}",
    r"\{[^{}\s][^{}]*\}",
    r"\$\{[^{}]+\}",
    r"\[[A-Za-z][A-Za-z0-9_.:-]*\]",
    r"%\d+\$[sd]|%\([a-z_]+\)[sd]|%[sd]",
    r"<<[^<>]+>>",
]
PLACEHOLDER_RE = re.compile("|".join(PLACEHOLDER_PATTERNS))
TAG_RE = re.compile(r"</?\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?/?>")
# Numbers incl. 1,000 / 1.000 / 3.5 / 3,5 ; normalised before comparison
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,   ]\d{3})*(?:[.,]\d+)?(?![\w])")
WORD_RE = re.compile(r"\w+", re.UNICODE)


def _strip_placeholders(text: str) -> str:
    return PLACEHOLDER_RE.sub(" ", TAG_RE.sub(" ", text))


def _normalise_number(raw: str) -> str:
    digits = re.sub(r"[^\d.,]", "", raw)
    # treat both , and . as possible decimal or thousands separators: keep digits only,
    # plus a marker if there's a decimal part with != 3 digits
    m = re.match(r"^(.*?)[.,](\d{1,2}|\d{4,})$", digits)
    if m:
        return re.sub(r"\D", "", m.group(1)) + "." + m.group(2)
    return re.sub(r"\D", "", digits)


def _issue(seg: Segment, check: str, sev: Severity, msg: str, **kw) -> Issue:
    return Issue(
        check=check,
        severity=sev,
        message=msg,
        item_id=seg.item.id,
        lang=seg.target_lang,
        source=seg.source,
        target=seg.target,
        row=seg.item.row,
        **kw,
    )


# --- checks ------------------------------------------------------------------------------


@segment_check("missing_translation")
def missing_translation(seg: Segment, ctx: Context):
    """Source text exists but the target is empty."""
    if seg.source.strip() and not seg.target.strip():
        yield _issue(seg, "missing_translation", Severity.ERROR, "Translation is missing")


@segment_check("untranslated")
def untranslated(seg: Segment, ctx: Context):
    """Target is identical to the source (likely copy-pasted, not translated)."""
    src, tgt = seg.source.strip(), seg.target.strip()
    if not src or src != tgt:
        return
    letters = _strip_placeholders(src)
    words = WORD_RE.findall(letters)
    if len(words) < 2 or not any(w.isalpha() for w in words):
        return  # single words, codes and numbers are often legitimately identical
    dnt = {t.lower() for t in (ctx.do_not_translate or [])}
    if src.lower() in dnt:
        return
    yield _issue(seg, "untranslated", Severity.WARNING, "Target is identical to source text")


@segment_check("placeholders")
def placeholders(seg: Segment, ctx: Context):
    """Placeholders / piping variables must be preserved exactly."""
    if not seg.target.strip():
        return
    src = Counter(PLACEHOLDER_RE.findall(seg.source))
    tgt = Counter(PLACEHOLDER_RE.findall(seg.target))
    if src == tgt:
        return
    missing = list((src - tgt).elements())
    extra = list((tgt - src).elements())
    parts = []
    if missing:
        parts.append(f"missing {missing}")
    if extra:
        parts.append(f"unexpected {extra}")
    yield _issue(
        seg,
        "placeholders",
        Severity.ERROR,
        "Placeholder mismatch: " + "; ".join(parts),
        extra={"missing": missing, "unexpected": extra},
    )


@segment_check("html_tags")
def html_tags(seg: Segment, ctx: Context):
    """HTML/markup tags must match between source and target."""
    if not seg.target.strip():
        return
    src = Counter(t.lower() for t in TAG_RE.findall(seg.source))
    tgt = Counter(t.lower() for t in TAG_RE.findall(seg.target))
    if src != tgt:
        yield _issue(
            seg,
            "html_tags",
            Severity.ERROR,
            f"Markup mismatch: source tags {dict(src)} vs target tags {dict(tgt)}",
        )


@segment_check("numbers")
def numbers(seg: Segment, ctx: Context):
    """Numbers (years, ages, amounts, scale points) should survive translation."""
    if not seg.target.strip():
        return
    src_text, tgt_text = _strip_placeholders(seg.source), _strip_placeholders(seg.target)
    src = Counter(_normalise_number(n) for n in NUMBER_RE.findall(src_text))
    tgt = Counter(_normalise_number(n) for n in NUMBER_RE.findall(tgt_text))
    if src == tgt:
        return
    missing = sorted((src - tgt).elements())
    extra = sorted((tgt - src).elements())
    if not missing:
        # extra numbers only: often legitimate (e.g. written-out number became digits)
        return
    yield _issue(
        seg,
        "numbers",
        Severity.WARNING,
        f"Numbers differ: missing {missing}" + (f", unexpected {extra}" if extra else ""),
    )


# Typical target/source character-length ratios relative to English. Rough, tune per corpus.
EXPECTED_RATIO = {"de": 1.3, "fr": 1.2, "es": 1.2, "it": 1.15, "pt": 1.15, "nl": 1.2,
                  "pl": 1.15, "ru": 1.15, "zh": 0.35, "ja": 0.55, "ko": 0.6}


@segment_check("length_ratio")
def length_ratio(seg: Segment, ctx: Context):
    """Target is suspiciously short or long compared with the source (possible omission)."""
    src, tgt = seg.source.strip(), seg.target.strip()
    if len(src) < 25 or not tgt or seg.item.role is Role.OPTION:
        return  # short labels and answer options legitimately vary a lot in length
    expected = EXPECTED_RATIO.get(seg.target_lang.split("-")[0].lower(), 1.0)
    ratio = len(tgt) / len(src) / expected
    if ratio < 0.5:
        yield _issue(seg, "length_ratio", Severity.WARNING,
                     f"Target is much shorter than expected (ratio {ratio:.2f}); "
                     "check for omitted content")
    elif ratio > 2.0:
        yield _issue(seg, "length_ratio", Severity.INFO,
                     f"Target is much longer than expected (ratio {ratio:.2f}); "
                     "check for added content")


@segment_check("question_punctuation")
def question_punctuation(seg: Segment, ctx: Context):
    """Questions should stay questions; Spanish questions need opening '¿'."""
    src, tgt = seg.source.strip(), seg.target.strip()
    if not tgt or seg.item.role is not Role.QUESTION:
        return
    q_marks = ("?", "？", "؟")
    if src.endswith(q_marks) and not tgt.rstrip(" »\"'”").endswith(q_marks):
        yield _issue(seg, "question_punctuation", Severity.WARNING,
                     "Source is a question but target does not end with a question mark")
    if seg.target_lang.lower().startswith("es") and "?" in tgt and "¿" not in tgt:
        yield _issue(seg, "question_punctuation", Severity.INFO,
                     "Spanish question is missing the opening '¿'",
                     suggestion="¿" + tgt if tgt.endswith("?") else None)


@segment_check("whitespace")
def whitespace(seg: Segment, ctx: Context):
    """Leading/trailing or doubled whitespace that differs from the source."""
    tgt = seg.target
    if not tgt:
        return
    if tgt != tgt.strip() and seg.source == seg.source.strip():
        yield _issue(seg, "whitespace", Severity.INFO, "Leading or trailing whitespace",
                     suggestion=tgt.strip())
    elif "  " in tgt and "  " not in seg.source:
        yield _issue(seg, "whitespace", Severity.INFO, "Double space in target",
                     suggestion=re.sub(r" {2,}", " ", tgt))
