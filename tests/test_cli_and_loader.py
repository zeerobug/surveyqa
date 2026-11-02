import json

import pytest

from surveyqa.cli import main
from surveyqa.loader import LoadError, load_survey


def test_load_sample(sample_path):
    s = load_survey(sample_path)
    assert s.source_lang == "en" and s.target_langs == ["es", "fr", "de"]
    assert len(s.scales()) == 2
    assert {i.id for i in s.scales()[0].items} >= {"Q5_1", "Q5_5"}


def test_load_errors(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("id,en\nQ1,Hello\n", encoding="utf-8")
    with pytest.raises(LoadError, match="No target"):
        load_survey(p)
    p.write_text("id,en,es\nQ1,a,b\nQ1,c,d\n", encoding="utf-8")
    with pytest.raises(LoadError, match="Duplicate id"):
        load_survey(p)
    with pytest.raises(LoadError, match="Source language"):
        load_survey(p, source_lang="fr")


def test_semicolon_csv(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("id;en;es\nQ1;Hello world;Hola mundo\n", encoding="utf-8")
    assert load_survey(p).target_langs == ["es"]


def test_xlsx_roundtrip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["id", "role", "en", "de"])
    wb.active.append(["Q1", "question", "Do you work?", "Arbeiten Sie?"])
    p = tmp_path / "s.xlsx"
    wb.save(p)
    s = load_survey(p)
    assert s.items[0].text("de") == "Arbeiten Sie?"


def test_cli_on_sample_finds_planted_errors(sample_path, tmp_path, capsys):
    out = tmp_path / "r.json"
    code = main(["check", str(sample_path), "--glossary", str(sample_path.parent / "glossary.csv"),
                 "--dnt", str(sample_path.parent / "do_not_translate.txt"),
                 "-o", str(out), "-o", str(tmp_path / "r.html"), "-o", str(tmp_path / "r.csv")])
    assert code == 1  # sample has errors -> CI should fail
    data = json.loads(out.read_text(encoding="utf-8"))
    hits = {(i["check"], i["item_id"], i["lang"]) for i in data["issues"]}
    expected = {
        ("placeholders", "I1", "fr"), ("untranslated", "I2", "fr"), ("numbers", "Q2", "de"),
        ("glossary", "Q3", "es"), ("do_not_translate", "Q4", "de"), ("html_tags", "Q5", "es"),
        ("scale_duplicate_labels", "Q5_5", "es"), ("register", "Q6", "es"),
        ("register", "Q6", "de"), ("numbers", "Q7", "fr"), ("missing_translation", "Q8", "fr"),
        ("question_punctuation", "Q9", "es"), ("whitespace", "Q9", "de"),
    }
    assert expected <= hits, expected - hits
    assert (tmp_path / "r.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_cli_fail_on_never(sample_path):
    assert main(["check", str(sample_path), "-q", "--fail-on", "never"]) == 0


def test_cli_unknown_check(sample_path):
    assert main(["check", str(sample_path), "--only", "nope"]) == 2
