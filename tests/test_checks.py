from conftest import make_survey

from surveyqa import run_checks
from surveyqa.checks import Context


def found(issues, check):
    return [i for i in issues if i.check == check]


def run(rows, check, targets=("es",), **ctx):
    return found(run_checks(make_survey(rows, targets), Context(**ctx), [check]), check)


# --- mechanical --------------------------------------------------------------------------

def test_missing_translation():
    assert run([{"id": "Q1", "en": "Hello there", "es": ""}], "missing_translation")
    assert not run([{"id": "Q1", "en": "Hello there", "es": "Hola"}], "missing_translation")


def test_untranslated_ignores_single_words_and_codes():
    assert run([{"id": "Q1", "en": "Please answer all", "es": "Please answer all"}],
               "untranslated")
    assert not run([{"id": "Q1", "en": "OK", "es": "OK"}], "untranslated")
    assert not run([{"id": "Q1", "en": "2024", "es": "2024"}], "untranslated")


def test_placeholders():
    bad = run([{"id": "Q1", "en": "Hi {TOKEN:FIRSTNAME}, see [Q3]", "es": "Hola, ver [Q3]"}],
              "placeholders")
    assert bad and "{TOKEN:FIRSTNAME}" in bad[0].message
    assert not run([{"id": "Q1", "en": "Hi ${name}", "es": "Hola ${name}"}], "placeholders")
    assert run([{"id": "Q1", "en": "Hi ${name}", "es": "Hola ${nombre}"}], "placeholders")


def test_html_tags():
    assert run([{"id": "Q1", "en": "<b>Bold</b> text", "es": "Texto"}], "html_tags")
    assert not run([{"id": "Q1", "en": "<b>Bold</b>", "es": "<b>Negrita</b>"}], "html_tags")


def test_numbers_handles_locale_separators():
    assert not run([{"id": "Q1", "en": "Over 1,000 people", "es": "Más de 1.000 personas"}],
                   "numbers")
    assert not run([{"id": "Q1", "en": "Rate 3.5", "es": "Tasa 3,5"}], "numbers")
    assert run([{"id": "Q1", "en": "Since 2024", "es": "Desde 2025"}], "numbers")


def test_numbers_ignores_placeholder_digits():
    assert not run([{"id": "Q1", "en": "See [Q3] for 2024", "es": "Ver [Q3] para 2024"}],
                   "numbers")


def test_length_ratio_skips_options():
    long_src = "This is a fairly long instruction about how to answer the next block."
    assert run([{"id": "I1", "en": long_src, "es": "Corto."}], "length_ratio")
    assert not run([{"id": "O1", "role": "option", "en": "Neither agree nor disagree",
                     "es": "Ni"}], "length_ratio")


def test_question_punctuation_spanish():
    issues = run([{"id": "Q1", "role": "question", "en": "Do you work?", "es": "Trabaja?"}],
                 "question_punctuation")
    assert issues and issues[0].suggestion == "¿Trabaja?"
    assert not run([{"id": "Q1", "role": "question", "en": "Do you work?", "es": "¿Trabaja?"}],
                   "question_punctuation")


def test_question_became_statement():
    assert run([{"id": "Q1", "role": "question", "en": "Do you work?", "fr": "Vous travaillez."}],
               "question_punctuation", targets=("fr",))


# --- scales ------------------------------------------------------------------------------

AGREE = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]


def scale_rows(sid, es_labels):
    return [{"id": f"{sid}_{n}", "role": "option", "scale": sid, "order": n, "en": en, "es": es}
            for n, (en, es) in enumerate(zip(AGREE, es_labels, strict=True), start=1)]


def test_scale_duplicate_labels():
    rows = scale_rows("A", ["Muy en desacuerdo", "En desacuerdo", "Neutral", "De acuerdo",
                            "De acuerdo"])
    issues = run(rows, "scale_duplicate_labels")
    assert len(issues) == 1 and issues[0].item_id == "A_5"


def test_scale_inconsistent_options_majority_suggestion():
    ok = ["Muy en desacuerdo", "En desacuerdo", "Neutral", "De acuerdo", "Muy de acuerdo"]
    odd = ok[:4] + ["Totalmente de acuerdo"]
    rows = scale_rows("A", ok) + scale_rows("B", ok) + scale_rows("C", odd)
    issues = run(rows, "scale_inconsistent_options")
    assert len(issues) == 1
    assert issues[0].item_id == "C_5" and issues[0].suggestion == "Muy de acuerdo"


def test_scale_length():
    rows = scale_rows("A", ["Muy en desacuerdo", "En desacuerdo", "", "De acuerdo",
                            "Muy de acuerdo"])
    assert run(rows, "scale_length")


# --- consistency -------------------------------------------------------------------------

def test_glossary():
    gl = [{"source": "employability", "lang": "es", "target": "empleabilidad"}]
    assert run([{"id": "Q1", "en": "Rate employability", "es": "Valore la capacidad de empleo"}],
               "glossary", glossary=gl)
    assert not run([{"id": "Q1", "en": "Rate employability", "es": "Valore la empleabilidad"}],
                   "glossary", glossary=gl)


def test_do_not_translate():
    assert run([{"id": "Q1", "en": "Erasmus+ exchange", "es": "intercambio Erasmus Plus"}],
               "do_not_translate", do_not_translate=["Erasmus+"])


def test_register_flags_minority():
    rows = [
        {"id": "Q1", "en": "Do you work?", "es": "¿Trabaja usted?"},
        {"id": "Q2", "en": "Do you study?", "es": "¿Estudia usted?"},
        {"id": "Q3", "en": "Is your job good?", "es": "¿Es bueno tu trabajo?"},
    ]
    issues = run(rows, "register")
    assert [i.item_id for i in issues] == ["Q3"]
