"""Command line interface.

    surveyqa check survey.csv --source en --langs es,fr,de -o report.html
    surveyqa check survey.xlsx --glossary glossary.csv --dnt "OECD,Erasmus+" --llm ollama/llama3.1
    surveyqa list-checks
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from surveyqa import __version__
from surveyqa.checks import REGISTRY, Context
from surveyqa.loader import LoadError, load_survey
from surveyqa.models import Severity
from surveyqa.report import to_csv, to_html, to_json, to_terminal
from surveyqa.runner import run_checks, select_checks


def _split(value: str | None) -> list[str] | None:
    return [v.strip() for v in value.split(",") if v.strip()] if value else None


def _load_glossary(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(fh)]


def _load_dnt(value: str | None) -> list[str] | None:
    if not value:
        return None
    p = Path(value)
    if p.exists():
        return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return _split(value)


def cmd_check(args: argparse.Namespace) -> int:
    try:
        survey = load_survey(args.file, source_lang=args.source, target_langs=_split(args.langs))
    except (LoadError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    llm = None
    if args.llm:
        from surveyqa.llm import LLMClient
        llm = LLMClient(args.llm, cache_dir=None if args.no_cache else ".surveyqa_cache")

    ctx = Context(
        glossary=_load_glossary(args.glossary) if args.glossary else None,
        do_not_translate=_load_dnt(args.dnt),
        llm=llm,
    )
    try:
        ids = select_checks(only=_split(args.only), skip=_split(args.skip),
                            llm_enabled=llm is not None)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    issues = run_checks(survey, ctx, ids)
    min_sev = Severity(args.min_severity)
    issues = [i for i in issues if i.severity.rank >= min_sev.rank]

    for out in args.output or []:
        p = Path(out)
        suffix = p.suffix.lower()
        if suffix == ".json":
            to_json(survey, issues, p)
        elif suffix == ".csv":
            to_csv(issues, p)
        elif suffix in {".html", ".htm"}:
            to_html(survey, issues, p)
        else:
            print(f"error: unknown output format for {out} (use .json/.csv/.html)",
                  file=sys.stderr)
            return 2

    if not args.quiet:
        print(to_terminal(survey, issues))
        if args.output:
            print()
        for out in args.output or []:
            print(f"  report written: {out}")

    if args.fail_on != "never":
        threshold = Severity(args.fail_on).rank
        if any(i.severity.rank >= threshold for i in issues):
            return 1
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    for spec in REGISTRY.values():
        tag = " [llm]" if spec.uses_llm else ""
        print(f"{spec.id:<28} {spec.category:<12} {spec.description}{tag}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="surveyqa",
                                description="QA for multilingual survey translations")
    p.add_argument("--version", action="version", version=f"surveyqa {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="check a translated survey file")
    c.add_argument("file", help=".csv, .tsv or .xlsx with one column per language")
    c.add_argument("--source", default="en", help="source language column (default: en)")
    c.add_argument("--langs", help="comma-separated target languages (default: all others)")
    c.add_argument("-o", "--output", action="append",
                   help="write report (.html, .csv, .json); repeatable")
    c.add_argument("--glossary", help="CSV with columns source,lang,target")
    c.add_argument("--dnt", help="do-not-translate terms: comma list or a file, one per line")
    c.add_argument("--llm", metavar="MODEL",
                   help="enable LLM checks with a LiteLLM model id, e.g. ollama/llama3.1, "
                        "anthropic/claude-sonnet-4-5, gpt-4o-mini")
    c.add_argument("--no-cache", action="store_true", help="disable the LLM response cache")
    c.add_argument("--only", help="run only these checks (comma-separated ids)")
    c.add_argument("--skip", help="skip these checks (comma-separated ids)")
    c.add_argument("--min-severity", default="info", choices=["info", "warning", "error"])
    c.add_argument("--fail-on", default="error", choices=["error", "warning", "info", "never"],
                   help="exit with code 1 if issues at this level exist (for CI)")
    c.add_argument("-q", "--quiet", action="store_true")
    c.set_defaults(func=cmd_check)

    ls = sub.add_parser("list-checks", help="list available checks")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
