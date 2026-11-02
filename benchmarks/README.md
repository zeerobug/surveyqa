# Benchmarks

`inject.py` takes a clean translated survey, injects one known error per trial, runs surveyqa and
reports recall per error type (taxonomy codes from `docs/error-taxonomy.md`), plus any new issues
on unrelated items (possible false positives) and the noise on the clean file.

```bash
python benchmarks/inject.py examples/clean_survey.csv --lang es --n 200 --seed 1
python benchmarks/inject.py examples/clean_survey.csv --lang es --n 200 --llm ollama/llama3.1
```

## Current mutators

| Code | Mutator | Notes |
|---|---|---|
| M1 | `blank` | empty a target cell |
| M2 | `copy_source` | replace target with source text |
| M3 | `drop_placeholder` | remove one placeholder |
| M5 | `change_number` | increment one number |
| M6 | `truncate` | cut a long target to a third |
| S2 | `collapse_scale_point` | copy the label of the neighbouring option |
| S3 | `swap_scale_ends` | swap the first and last option |

These first mutators are mechanical, so deterministic checks catch all of them. The benchmark only
becomes informative with **language-aware meaning mutators**, which are the next thing to build:

- D1 negation removal / insertion (per language: *not, no, nicht, kein, ne…pas, no*)
- D2 quantifier swap (*never → rarely, always → often, nunca → rara vez, jamais → rarement*)
- D3 intensity change (*very → somewhat, muy → bastante*)
- D4 time reference change (*12 months → 6 months, last year → this year*)
- S4/S5 midpoint replaced with "Don't know"

These are where the LLM checks have to earn their place, and where comparing models
(local vs hosted) produces a publishable table.

## Data

Use only public or self-written questionnaires here. Never commit client data.
