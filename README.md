https://haqfinder.onrender.com/
# HAQfinder

**Discover. Understand. Claim.**

HAQfinder helps Indian citizens discover public welfare schemes they may be eligible for, understand the criteria in plain language, and prepare to claim them. It is part of the ACE Builders Hackathon 2026, Problem Statement 5: Citizens and Public Services.

## Features (MVP scope)

- A curated scheme catalogue in `data/schemes.json` (central and state schemes).
- An eligibility engine that compares a citizen profile against structured scheme conditions and labels results as "Likely eligible", "Possibly eligible" or "Not eligible" with reasons.
- A FastAPI backend (`app/main.py`) serving the catalogue and eligibility checks.

## Windows setup

```bat
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Run the test suite:

```bat
python -m pytest -q
```

## Disclaimer

- HAQfinder is an informational tool. It is **not legal advice** and is not an official government service.
- Scheme details are summarized from public sources and may be outdated. **Always verify on the official portal before applying.**
- A "Likely eligible" result is **not a guarantee** of enrolment or benefit. Final eligibility is decided by the scheme's authority.

## Scheme data: `data/schemes.json`

The file is a JSON object with a single key, `schemes`, whose value is a list of scheme objects. Each scheme has these fields:

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique slug for the scheme (e.g. `pm-kisan`). |
| `name` | string | Human-readable scheme name. |
| `category` | string | One of: `education`, `agriculture`, `health`, `housing`, `pension`, `finance`, `employment`. |
| `description` | string | Short plain-language summary of the scheme. |
| `state` | string or null | `null` for central schemes, otherwise the state name. |
| `eligibility` | object | Structured conditions (see below). Keys are optional. |
| `required_documents` | list of strings | Documents usually needed to apply. |
| `application_steps` | list of strings | Ordered steps to apply. |
| `deadline` | string or null | `YYYY-MM-DD`, or `null` if no fixed deadline is known. |
| `official_link` | string | Official portal or landing page. |
| `source_url` | string | Public page the criteria were summarized from. |
| `last_verified` | string | Date the entry was last checked, `YYYY-MM-DD`. |
| `verification_note` | string | Standard note: "Criteria summarized from public sources; verify on official portal before applying". |

### Eligibility conditions

All conditions present in an `eligibility` object are checked against the citizen profile. Missing profile values produce "unknown" for that condition rather than a failure.

| Condition | Type | Meaning |
| --- | --- | --- |
| `income_max` | integer | Maximum annual household income in INR. |
| `age_min` | integer | Minimum age in years. |
| `age_max` | integer | Maximum age in years. |
| `occupation_in` | list of strings | Citizen occupation must be one of these. |
| `education_in` | list of strings | Citizen education level must be one of these. |
| `category_in` | list of strings | Social category; one of `SC`, `ST`, `OBC`, `General`, `Minority`, `EWS`. |
| `residence_state` | list of strings | Citizen's state of residence must be one of these. |
| `is_rural` | boolean | Citizen lives in a rural area (`true`) or urban area (`false`). |
| `has_disability` | boolean | Citizen has a disability (`true`) or not (`false`). |
| `gender_in` | list of strings | Citizen gender must be one of these. |

Schemes must not request Aadhaar, PAN or bank account details as profile fields.

## Sample profiles

These profiles are intended for manual and automated checks of the eligibility engine:

1. **UP B.Tech student from a farmer family with low income** - age 20, education: Graduate (in progress), occupation: student, category: OBC, residence: Uttar Pradesh, rural, annual family income Rs 2,00,000, family occupation: farmer.
2. **Rural 65-year-old BPL person** - age 65, occupation: daily wage labourer, category: General, residence: Bihar, rural, annual income Rs 36,000, below poverty line.
3. **Urban high-income salaried person** - age 32, occupation: salaried employee, education: Graduate, category: General, residence: Maharashtra, urban, annual income Rs 18,00,000.
4. **SC student from Bihar** - age 19, education: Class 12 pass, occupation: student, category: SC, residence: Bihar, rural, annual family income Rs 1,20,000.
5. **Farmer in Punjab** - age 45, occupation: farmer, category: General, residence: Punjab, rural, annual income Rs 1,50,000, owns agricultural land.
