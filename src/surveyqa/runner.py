"""Run the registered checks over a survey."""

from __future__ import annotations

import logging

from surveyqa.checks import REGISTRY, Context
from surveyqa.models import Issue, Survey

log = logging.getLogger(__name__)


def select_checks(only: list[str] | None = None, skip: list[str] | None = None,
                  llm_enabled: bool = False) -> list[str]:
    ids = list(REGISTRY)
    if only:
        unknown = set(only) - set(ids)
        if unknown:
            raise ValueError(f"Unknown check(s): {sorted(unknown)}")
        ids = [i for i in ids if i in only]
    if skip:
        ids = [i for i in ids if i not in skip]
    if not llm_enabled:
        ids = [i for i in ids if not REGISTRY[i].uses_llm]
    return ids


def run_checks(survey: Survey, ctx: Context | None = None,
               checks: list[str] | None = None) -> list[Issue]:
    ctx = ctx or Context()
    ids = checks if checks is not None else select_checks(llm_enabled=ctx.llm is not None)
    issues: list[Issue] = []
    segments = survey.segments()
    for cid in ids:
        spec = REGISTRY[cid]
        try:
            if spec.kind == "segment":
                for seg in segments:
                    issues.extend(spec.fn(seg, ctx) or [])
            else:
                issues.extend(spec.fn(survey, ctx) or [])
        except Exception as e:  # one broken check must not kill the run
            log.exception("Check %s failed", cid)
            from surveyqa.models import Severity
            issues.append(Issue(check=cid, severity=Severity.INFO,
                                message=f"Check crashed: {e!r}"))
    issues.sort(key=lambda i: (i.row or 0, i.lang or "", -i.severity.rank, i.check))
    return issues
