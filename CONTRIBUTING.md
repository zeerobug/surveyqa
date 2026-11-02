# Contributing to surveyqa

Thanks for helping. The most useful contributions, in order:

1. **Real translation errors** (anonymized) mapped to [docs/error-taxonomy.md](docs/error-taxonomy.md)
2. **New checks** for error types marked *todo*
3. **Language support**: register markers, expected length ratios, punctuation rules
4. Input formats (LimeSurvey `.lss`, XLSForm, Qualtrics `.qsf`)

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check .
```

## Writing a check

A check is a generator function registered with a decorator. Per-segment checks see one item in
one target language; survey checks see everything (for cross-item and scale rules).

```python
# src/surveyqa/checks/mechanical.py
from surveyqa.checks import Context, segment_check
from surveyqa.models import Issue, Segment, Severity

@segment_check("emoji")
def emoji(seg: Segment, ctx: Context):
    """Target contains emoji the source doesn't have."""
    if has_emoji(seg.target) and not has_emoji(seg.source):
        yield Issue(check="emoji", severity=Severity.INFO, message="Unexpected emoji",
                    item_id=seg.item.id, lang=seg.target_lang, row=seg.item.row,
                    source=seg.source, target=seg.target)
```

Rules of thumb:

- **Precision over recall.** A noisy check gets switched off by users. If a rule is heuristic,
  use `info` or `warning`, never `error`.
- The first line of the docstring is shown in `surveyqa list-checks`.
- Add a test in `tests/` with at least one positive and one negative case.
- If the check needs an LLM, pass `uses_llm=True`, and read the client from `ctx.llm`.
- Map it to an error code in `docs/error-taxonomy.md`.

## Pull requests

Keep PRs small, include tests, and describe the error type in the PR description.
