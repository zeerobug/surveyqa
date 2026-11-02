"""Core data model.

A Survey is a list of Items. Each Item has a role (question, instruction, option, ...)
and a text per language. Answer options that belong together are grouped into a Scale,
so scale-level checks (order, duplicates, polarity) can look at them as a unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(str, Enum):
    QUESTION = "question"
    INSTRUCTION = "instruction"
    OPTION = "option"
    TITLE = "title"
    OTHER = "other"

    @classmethod
    def parse(cls, value: str | None) -> Role:
        if not value:
            return cls.OTHER
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.OTHER


class Severity(str, Enum):
    ERROR = "error"      # will very likely break data or comparability
    WARNING = "warning"  # needs a human look
    INFO = "info"        # stylistic / heuristic

    @property
    def rank(self) -> int:
        return {"error": 3, "warning": 2, "info": 1}[self.value]


@dataclass
class Item:
    """One translatable unit (a question text, an instruction, one answer option...)."""

    id: str
    role: Role
    texts: dict[str, str]          # lang code -> text
    question: str | None = None    # parent question id, for options
    scale: str | None = None       # scale id, for options
    order: int | None = None       # position within the scale
    row: int | None = None         # line number in the input file, for reporting

    def text(self, lang: str) -> str:
        return self.texts.get(lang, "") or ""


@dataclass
class Segment:
    """A source/target pair for one item in one target language. What most checks see."""

    item: Item
    source_lang: str
    target_lang: str

    @property
    def source(self) -> str:
        return self.item.text(self.source_lang)

    @property
    def target(self) -> str:
        return self.item.text(self.target_lang)


@dataclass
class Scale:
    id: str
    items: list[Item]

    def ordered(self) -> list[Item]:
        return sorted(self.items, key=lambda i: (i.order is None, i.order or 0))


@dataclass
class Survey:
    items: list[Item]
    source_lang: str
    target_langs: list[str]
    name: str = "survey"

    def segments(self, lang: str | None = None) -> list[Segment]:
        langs = [lang] if lang else self.target_langs
        return [Segment(i, self.source_lang, tl) for tl in langs for i in self.items]

    def scales(self) -> list[Scale]:
        groups: dict[str, list[Item]] = {}
        for item in self.items:
            if item.scale:
                groups.setdefault(item.scale, []).append(item)
        return [Scale(sid, items) for sid, items in groups.items()]


@dataclass
class Issue:
    check: str
    severity: Severity
    message: str
    item_id: str | None = None
    lang: str | None = None
    source: str | None = None
    target: str | None = None
    suggestion: str | None = None
    row: int | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "item_id": self.item_id,
            "lang": self.lang,
            "source": self.source,
            "target": self.target,
            "suggestion": self.suggestion,
            "row": self.row,
        }
        if self.extra:
            d["extra"] = self.extra
        return d
