from pathlib import Path

import pytest

from surveyqa.models import Item, Role, Survey

EXAMPLES = Path(__file__).parent.parent / "examples"


def make_survey(rows: list[dict], targets=("es",)) -> Survey:
    """rows: dicts with id, en, es, ... and optional role/scale/order."""
    items = []
    for n, r in enumerate(rows, start=2):
        items.append(Item(
            id=r["id"], role=Role.parse(r.get("role")),
            texts={k: v for k, v in r.items() if k not in {"id", "role", "scale", "order"}},
            scale=r.get("scale"), order=r.get("order"), row=n,
        ))
    return Survey(items=items, source_lang="en", target_langs=list(targets))


@pytest.fixture
def sample_path() -> Path:
    return EXAMPLES / "sample_survey.csv"
