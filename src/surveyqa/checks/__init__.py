"""Check registry.

A check is a function decorated with @segment_check (runs once per item x target language)
or @survey_check (sees the whole survey, for cross-item and scale-level checks).

Adding a check = write a function in any module under surveyqa.checks and import the module
in `_load_builtin_checks`. See CONTRIBUTING.md.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from surveyqa.models import Issue, Segment, Survey

SegmentFn = Callable[[Segment, "Context"], Iterable[Issue]]
SurveyFn = Callable[[Survey, "Context"], Iterable[Issue]]


@dataclass
class CheckSpec:
    id: str
    kind: str  # "segment" | "survey"
    fn: Callable
    description: str
    category: str
    uses_llm: bool = False


REGISTRY: dict[str, CheckSpec] = {}


def _register(kind: str, id: str, category: str, uses_llm: bool):
    def deco(fn):
        if id in REGISTRY:
            raise ValueError(f"Duplicate check id: {id}")
        REGISTRY[id] = CheckSpec(
            id=id,
            kind=kind,
            fn=fn,
            description=(fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
            category=category,
            uses_llm=uses_llm,
        )
        return fn

    return deco


def segment_check(id: str, category: str = "mechanical", uses_llm: bool = False):
    return _register("segment", id, category, uses_llm)


def survey_check(id: str, category: str = "consistency", uses_llm: bool = False):
    return _register("survey", id, category, uses_llm)


@dataclass
class Context:
    """Shared configuration passed to every check."""

    glossary: list[dict] | None = None        # rows: source, lang, target
    do_not_translate: list[str] | None = None
    llm: object | None = None                 # surveyqa.llm.LLMClient when enabled


def _load_builtin_checks() -> None:
    from surveyqa.checks import consistency, llm_checks, mechanical, scales  # noqa: F401


_load_builtin_checks()
