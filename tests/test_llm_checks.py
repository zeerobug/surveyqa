"""LLM checks are tested with a fake client so CI never needs an API key."""

import json

import pytest
from conftest import make_survey

from surveyqa import run_checks
from surveyqa.checks import Context
from surveyqa.llm import LLMClient, LLMError, parse_json


class FakeLLM(LLMClient):
    def __init__(self, reply):
        super().__init__("fake", cache_dir=None)
        self.reply = reply
        self.prompts = []

    def _complete(self, system, user):
        self.prompts.append(user)
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


def test_meaning_drift_maps_model_output():
    llm = FakeLLM({"issues": [{"type": "quantifier_changed", "severity": "error",
                               "explanation": "'never' became 'rarely'",
                               "suggestion": "¿Nunca ha sido contactado?"}]})
    survey = make_survey([{"id": "Q1", "role": "question", "en": "Have you never been contacted?",
                           "es": "¿Ha sido contactado rara vez?"}])
    issues = run_checks(survey, Context(llm=llm), ["meaning_drift"])
    assert len(issues) == 1
    assert issues[0].severity.value == "error"
    assert "quantifier_changed" in issues[0].message
    assert issues[0].suggestion.startswith("¿Nunca")


def test_meaning_drift_skips_options():
    llm = FakeLLM({"issues": []})
    survey = make_survey([{"id": "O1", "role": "option", "en": "Agree", "es": "De acuerdo"}])
    run_checks(survey, Context(llm=llm), ["meaning_drift"])
    assert llm.prompts == []


def test_scale_equivalence_points_to_item():
    llm = FakeLLM({"issues": [{"position": 2, "severity": "error",
                               "explanation": "polarity reversed", "suggestion": "En desacuerdo"}]})
    rows = [{"id": f"A_{n}", "role": "option", "scale": "A", "order": n, "en": en, "es": es}
            for n, (en, es) in enumerate([("Disagree", "De acuerdo"), ("Agree", "En desacuerdo")],
                                         start=1)]
    issues = run_checks(make_survey(rows), Context(llm=llm), ["scale_equivalence"])
    assert issues and issues[0].item_id == "A_2"


def test_llm_checks_disabled_without_client():
    survey = make_survey([{"id": "Q1", "en": "Hello", "es": "Hola"}])
    assert run_checks(survey, Context()) == []


@pytest.mark.parametrize("raw", [
    '{"issues": []}',
    '```json\n{"issues": []}\n```',
    'Here you go:\n{"issues": []}',
])
def test_parse_json_tolerant(raw):
    assert parse_json(raw) == {"issues": []}


def test_parse_json_raises():
    with pytest.raises(LLMError):
        parse_json("no json here")
