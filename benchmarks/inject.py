"""Synthetic error injection for benchmarking checks.

Takes a *clean* translated survey, injects known errors, runs surveyqa, and reports
precision / recall per check. This is how we'll measure (and publish) how good each
check and each LLM is.

    python benchmarks/inject.py clean_survey.csv --lang es --n 50 --seed 1 [--llm MODEL]

Status: first version. Mutators are simple on purpose; add more (and language-aware ones)
over time. Results go to stdout as a table and to benchmarks/results/*.json.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from surveyqa import run_checks
from surveyqa.checks import Context
from surveyqa.loader import load_survey
from surveyqa.models import Item, Role, Survey


@dataclass
class Injected:
    item_id: str
    lang: str
    error_code: str          # taxonomy code, e.g. M3
    expected_checks: set[str]
    touched: frozenset[str] = frozenset()  # other ids legitimately affected (scale, swapped item)


# Each mutator: (survey, lang, rng) -> Injected | None. Mutates the survey in place.

def drop_placeholder(s: Survey, lang: str, rng: random.Random):
    from surveyqa.checks.mechanical import PLACEHOLDER_RE
    cands = [i for i in s.items if PLACEHOLDER_RE.search(i.text(lang))]
    if not cands:
        return None
    it = rng.choice(cands)
    it.texts[lang] = PLACEHOLDER_RE.sub("", it.text(lang), count=1)
    return Injected(it.id, lang, "M3", {"placeholders"})


def change_number(s: Survey, lang: str, rng: random.Random):
    cands = [i for i in s.items if re.search(r"\d", i.text(lang))]
    if not cands:
        return None
    it = rng.choice(cands)
    it.texts[lang] = re.sub(r"\d+", lambda m: str(int(m.group()) + 1), it.text(lang), count=1)
    return Injected(it.id, lang, "M5", {"numbers"})


def blank(s: Survey, lang: str, rng: random.Random):
    cands = [i for i in s.items if i.text(lang).strip()]
    it = rng.choice(cands)
    it.texts[lang] = ""
    return Injected(it.id, lang, "M1", {"missing_translation", "scale_length"},
                    frozenset({it.scale} if it.scale else set()))


def copy_source(s: Survey, lang: str, rng: random.Random):
    cands = [i for i in s.items if len(i.text(s.source_lang).split()) >= 3]
    if not cands:
        return None
    it = rng.choice(cands)
    it.texts[lang] = it.text(s.source_lang)
    return Injected(it.id, lang, "M2", {"untranslated"})


def collapse_scale_point(s: Survey, lang: str, rng: random.Random):
    scales = [sc for sc in s.scales() if len(sc.items) >= 3]
    if not scales:
        return None
    items = rng.choice(scales).ordered()
    a, b = items[-1], items[-2]
    a.texts[lang] = b.text(lang)
    return Injected(a.id, lang, "S2", {"scale_duplicate_labels", "scale_equivalence"},
                    frozenset({b.id, a.scale}))


def swap_scale_ends(s: Survey, lang: str, rng: random.Random):
    scales = [sc for sc in s.scales() if len(sc.items) >= 3]
    if not scales:
        return None
    items = rng.choice(scales).ordered()
    first, last = items[0], items[-1]
    first.texts[lang], last.texts[lang] = last.text(lang), first.text(lang)
    return Injected(first.id, lang, "S3", {"scale_equivalence", "scale_inconsistent_options"},
                    frozenset({last.id, first.scale}))


def truncate(s: Survey, lang: str, rng: random.Random):
    cands = [i for i in s.items if i.role is not Role.OPTION and len(i.text(lang)) > 60]
    if not cands:
        return None
    it = rng.choice(cands)
    it.texts[lang] = it.text(lang)[: len(it.text(lang)) // 3].rstrip() + "."
    return Injected(it.id, lang, "M6", {"length_ratio", "meaning_drift"})


MUTATORS = [drop_placeholder, change_number, blank, copy_source, collapse_scale_point,
            swap_scale_ends, truncate]


def run_trial(clean: Survey, lang: str, rng: random.Random, ctx: Context):
    s = copy.deepcopy(clean)
    s.target_langs = [lang]
    inj = None
    for mut in rng.sample(MUTATORS, len(MUTATORS)):
        inj = mut(s, lang, rng)
        if inj:
            break
    if inj is None:
        return None, []
    return inj, run_checks(s, ctx)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--source", default="en")
    ap.add_argument("--lang", required=True)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--llm")
    args = ap.parse_args()

    clean = load_survey(args.file, args.source, [args.lang])
    llm = None
    if args.llm:
        from surveyqa.llm import LLMClient
        llm = LLMClient(args.llm)
    ctx = Context(llm=llm)
    baseline = {(i.check, i.item_id) for i in run_checks(clean, ctx)}

    rng = random.Random(args.seed)
    stats = defaultdict(lambda: {"injected": 0, "detected": 0})
    false_pos = 0
    for _ in range(args.n):
        inj, issues = run_trial(clean, args.lang, rng, ctx)
        if inj is None:
            continue
        stats[inj.error_code]["injected"] += 1
        new = {(i.check, i.item_id) for i in issues} - baseline
        if any(c in inj.expected_checks and iid == inj.item_id for c, iid in new):
            stats[inj.error_code]["detected"] += 1
        ok_ids = {inj.item_id, *inj.touched}
        # items sharing a source label with a touched item are legitimately flagged by
        # cross-scale consistency checks (they are the other half of the inconsistency)
        labels = {i.text(clean.source_lang) for i in clean.items if i.id in ok_ids}
        ok_ids |= {i.id for i in clean.items if i.text(clean.source_lang) in labels}
        false_pos += sum(1 for _, iid in new if iid not in ok_ids)

    print(f"{'error':<6} {'injected':>9} {'detected':>9} {'recall':>7}")
    for code, st in sorted(stats.items()):
        print(f"{code:<6} {st['injected']:>9} {st['detected']:>9} "
              f"{st['detected'] / st['injected']:>7.0%}")
    print(f"\nnew issues on other items (possible false positives): {false_pos}")
    print(f"issues on the clean survey (baseline noise): {len(baseline)}")

    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    model = (args.llm or "nollm").replace("/", "-")
    name = f"{Path(args.file).stem}_{args.lang}_{model}_{args.seed}.json"
    (out / name).write_text(json.dumps({"stats": stats, "false_positives": false_pos,
                                        "baseline": len(baseline)}, indent=2))


if __name__ == "__main__":
    main()


__all__ = ["MUTATORS", "Injected", "Item"]
