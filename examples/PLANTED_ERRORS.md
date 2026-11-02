# Planted errors in `sample_survey.csv`

The sample survey contains deliberate mistakes so you can see what each check catches.
"Deterministic" errors are found without an LLM; "LLM" errors need `--llm`.

| Item | Lang | Error | Caught by |
|------|------|-------|-----------|
| I1 | fr | `{TOKEN:FIRSTNAME}` placeholder dropped | `placeholders` (deterministic) |
| I2 | fr | Left in English | `untranslated` (deterministic) |
| Q2 | de | Year 2024 changed to 2025 | `numbers` (deterministic) |
| Q2 | es | "never" became "rarely" (*rara vez*) | `meaning_drift` (LLM) |
| Q3 | es | Glossary term *empleabilidad* not used | `glossary` (deterministic) |
| Q4 | de | "Erasmus+" altered to "Erasmus Plus" | `do_not_translate` (deterministic, with `--dnt`) |
| Q5 | es | `<b>` markup dropped | `html_tags` (deterministic) |
| Q5 scale | es | "Agree" and "Strongly agree" both *De acuerdo* | `scale_duplicate_labels` (deterministic) |
| Q5 scale | fr | Scale polarity reversed | `scale_equivalence` (LLM) |
| Q5 vs Q6 | fr | "Agree" translated *Pas d'accord* in one scale, *D'accord* in the other | `scale_inconsistent_options` (deterministic) |
| Q6 | de | "Strongly agree" translated two different ways across scales | `scale_inconsistent_options` (deterministic) |
| Q6 | es, de | Informal address (tú / du) in an otherwise formal survey | `register` (deterministic) |
| Q7 | fr | "in euros (for example 2500)" omitted | `numbers` (deterministic), `meaning_drift` (LLM) |
| Q8 | fr | Translation missing | `missing_translation` (deterministic) |
| Q9 | es | Missing opening "¿" | `question_punctuation` (deterministic) |
| Q9 | de | Double space | `whitespace` (deterministic) |
