# Error taxonomy

This is the spec for surveyqa. Every check should map to one of these error types, and every error
type should eventually have (a) at least one check, (b) test cases, and (c) benchmark items.

Severity guide:

- **error**: will very likely break data collection or comparability
- **warning**: needs a human decision
- **info**: stylistic or heuristic

## 1. Mechanical

| Code | Description | Example | Severity | Check |
|---|---|---|---|---|
| M1 | Missing translation | empty cell | error | `missing_translation` |
| M2 | Untranslated segment | French cell still in English | warning | `untranslated` |
| M3 | Placeholder / piping broken | `{TOKEN:FIRSTNAME}` dropped | error | `placeholders` |
| M4 | Markup broken | `<b>` lost | error | `html_tags` |
| M5 | Number changed | 2024 → 2025 | warning | `numbers` |
| M6 | Omission / addition (length) | half the sentence missing | warning | `length_ratio` |
| M7 | Punctuation changes item type | question became a statement | warning | `question_punctuation` |
| M8 | Whitespace | trailing / double spaces | info | `whitespace` |

## 2. Answer scales

| Code | Description | Example | Severity | Check |
|---|---|---|---|---|
| S1 | Different number of points | 5-point → 4-point | error | `scale_length` |
| S2 | Collapsed points | "Agree" and "Strongly agree" both *De acuerdo* | error | `scale_duplicate_labels` |
| S3 | Reversed order / polarity | disagree↔agree swapped | error | `scale_equivalence` (LLM) |
| S4 | Uneven intensity | "Somewhat" → "Totally" | warning | `scale_equivalence` (LLM) |
| S5 | Midpoint changed | "Neither…nor" → "Don't know" | error | `scale_equivalence` (LLM) |
| S6 | Same label, different translations across scales | | warning | `scale_inconsistent_options` |

## 3. Meaning

| Code | Description | Example | Severity | Check |
|---|---|---|---|---|
| D1 | Negation changed or dropped | "not satisfied" → "satisfied" | error | `meaning_drift` (LLM) |
| D2 | Quantifier / frequency changed | "never" → "rarely" | error | `meaning_drift` (LLM) |
| D3 | Intensity changed | "very important" → "important" | warning | `meaning_drift` (LLM) |
| D4 | Time reference changed | "last 12 months" → "last year" | warning | `meaning_drift` (LLM) |
| D5 | Became double-barreled / leading | | warning | `meaning_drift` (LLM) |
| D6 | Wrong subject / referent | "your university" → "the university" | warning | `meaning_drift` (LLM) |
| D7 | Key term mistranslated | | error | `meaning_drift` (LLM) |

## 4. Consistency

| Code | Description | Example | Severity | Check |
|---|---|---|---|---|
| C1 | Glossary violation | *capacidad de empleo* instead of *empleabilidad* | warning | `glossary` |
| C2 | Protected term altered | "Erasmus+" → "Erasmus Plus" | error | `do_not_translate` |
| C3 | Mixed register | tú and usted in one questionnaire | warning | `register` |
| C4 | Same source sentence translated differently | repeated instructions | warning | *todo* |

## 5. Localization and cultural fit (mostly LLM, mostly warnings)

| Code | Description | Example | Check |
|---|---|---|---|
| L1 | Education-system terms that don't map | "college", "GPA", "sixth form" | *todo* |
| L2 | Currency, units, date formats | "$", "miles", MM/DD | *todo* |
| L3 | Culturally loaded or inapplicable examples | | *todo* |
| L4 | Gender-inclusive form inconsistent | Estimado/a vs Estimado | *todo* |

## Contributing examples

Real errors are the most valuable input for this project. Please open an issue with:
source text, translation, language pair, error code from this table, and the corrected version.
Remove anything confidential first.
