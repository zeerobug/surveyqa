"""Load bilingual / multilingual survey tables.

Expected layout (one row per translatable item):

    id, role, question, scale, order, en, es, fr, de

- `id`       unique item id (required)
- `role`     question | instruction | option | title | other (optional, default other)
- `question` parent question id, for options (optional)
- `scale`    scale id; options sharing a scale are checked together (optional)
- `order`    position of the option inside its scale (optional)
- every other column is treated as a language column (header = language code)

Supported formats: .csv, .tsv, .xlsx (needs `pip install surveyqa[xlsx]`).
"""

from __future__ import annotations

import csv
from pathlib import Path

from surveyqa.models import Item, Role, Survey

META_COLUMNS = {"id", "role", "question", "scale", "order", "notes", "comment"}


class LoadError(ValueError):
    pass


def _read_rows(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            sample = fh.read(4096)
            fh.seek(0)
            delimiter = "\t" if suffix == ".tsv" else _sniff_delimiter(sample)
            return list(csv.DictReader(fh, delimiter=delimiter))
    if suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError as e:  # pragma: no cover
            raise LoadError("Reading .xlsx needs openpyxl: pip install 'surveyqa[xlsx]'") from e
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        header = [str(h).strip() if h is not None else "" for h in rows[0]]
        return [
            {h: ("" if v is None else str(v)) for h, v in zip(header, r, strict=False) if h}
            for r in rows[1:]
        ]
    raise LoadError(f"Unsupported file type: {suffix} (use .csv, .tsv or .xlsx)")


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def load_survey(
    path: str | Path,
    source_lang: str = "en",
    target_langs: list[str] | None = None,
) -> Survey:
    path = Path(path)
    rows = _read_rows(path)
    if not rows:
        raise LoadError(f"{path} contains no rows")

    columns = [c.strip() for c in rows[0].keys() if c]
    lower = {c.lower(): c for c in columns}
    if "id" not in lower:
        raise LoadError("Missing required column 'id'")
    lang_cols = [c for c in columns if c.lower() not in META_COLUMNS]
    if source_lang not in lang_cols:
        raise LoadError(f"Source language column '{source_lang}' not found. Columns: {columns}")

    targets = target_langs or [c for c in lang_cols if c != source_lang]
    missing = [t for t in targets if t not in lang_cols]
    if missing:
        raise LoadError(f"Target language column(s) not found: {missing}")
    if not targets:
        raise LoadError("No target language columns found")

    def get(row: dict, key: str) -> str:
        col = lower.get(key)
        return (row.get(col) or "").strip() if col else ""

    items: list[Item] = []
    seen: set[str] = set()
    for n, row in enumerate(rows, start=2):  # row 1 is the header
        item_id = get(row, "id")
        if not item_id:
            continue
        if item_id in seen:
            raise LoadError(f"Duplicate id '{item_id}' on row {n}")
        seen.add(item_id)
        order_raw = get(row, "order")
        items.append(
            Item(
                id=item_id,
                role=Role.parse(get(row, "role")),
                texts={lang: (row.get(lang) or "") for lang in [source_lang, *targets]},
                question=get(row, "question") or None,
                scale=get(row, "scale") or None,
                order=int(order_raw) if order_raw.lstrip("-").isdigit() else None,
                row=n,
            )
        )
    return Survey(items=items, source_lang=source_lang, target_langs=targets, name=path.stem)
