"""Scale-level checks. Answer scales are where translation errors hurt comparability most."""

from __future__ import annotations

from surveyqa.checks import Context, survey_check
from surveyqa.models import Issue, Severity, Survey


@survey_check("scale_duplicate_labels", category="scale")
def scale_duplicate_labels(survey: Survey, ctx: Context):
    """Two different source options were translated to the same label within one scale."""
    for scale in survey.scales():
        for lang in survey.target_langs:
            seen: dict[str, str] = {}
            for item in scale.ordered():
                tgt = item.text(lang).strip().lower()
                if not tgt:
                    continue
                if tgt in seen and item.text(survey.source_lang).strip().lower() != seen[tgt]:
                    yield Issue(
                        check="scale_duplicate_labels",
                        severity=Severity.ERROR,
                        message=f"Scale '{scale.id}': option '{item.id}' has the same "
                                f"translation as another option with a different source label",
                        item_id=item.id, lang=lang, row=item.row,
                        source=item.text(survey.source_lang), target=item.text(lang),
                    )
                seen.setdefault(tgt, item.text(survey.source_lang).strip().lower())


@survey_check("scale_inconsistent_options", category="scale")
def scale_inconsistent_options(survey: Survey, ctx: Context):
    """The same option label (e.g. 'Strongly agree') is translated differently across scales."""
    for lang in survey.target_langs:
        by_source: dict[str, dict[str, list[str]]] = {}
        for item in survey.items:
            if not item.scale:
                continue
            src = item.text(survey.source_lang).strip()
            tgt = item.text(lang).strip()
            if src and tgt:
                by_source.setdefault(src.lower(), {}).setdefault(tgt, []).append(item.id)
        for variants in by_source.values():
            if len(variants) > 1:
                # majority variant is the suggestion; flag the others.
                # On a tie there is no safe suggestion, so flag every variant.
                counts = sorted((len(v) for v in variants.values()), reverse=True)
                tie = counts[0] == counts[1]
                majority = None if tie else max(variants, key=lambda v: len(variants[v]))
                for variant, ids in variants.items():
                    if variant == majority:
                        continue
                    for item_id in ids:
                        item = next(i for i in survey.items if i.id == item_id)
                        yield Issue(
                            check="scale_inconsistent_options",
                            severity=Severity.WARNING,
                            message=f"Option label translated inconsistently across scales: "
                                    f"here '{variant}', elsewhere "
                                    + ", ".join(f"'{v}'" for v in variants if v != variant)
                                    + (" (no majority variant)" if tie else ""),
                            item_id=item_id, lang=lang, row=item.row,
                            source=item.text(survey.source_lang), target=variant,
                            suggestion=majority,
                        )


@survey_check("scale_length", category="scale")
def scale_length(survey: Survey, ctx: Context):
    """A scale has fewer translated options than source options."""
    for scale in survey.scales():
        n_src = sum(1 for i in scale.items if i.text(survey.source_lang).strip())
        for lang in survey.target_langs:
            n_tgt = sum(1 for i in scale.items if i.text(lang).strip())
            if n_tgt and n_tgt != n_src:
                yield Issue(
                    check="scale_length",
                    severity=Severity.ERROR,
                    message=f"Scale '{scale.id}' has {n_src} source options but {n_tgt} "
                            f"translated options",
                    item_id=scale.id, lang=lang, row=scale.ordered()[0].row,
                )
