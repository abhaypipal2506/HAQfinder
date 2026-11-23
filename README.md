# HAQfinder

**Discover. Understand. Claim.**

HAQfinder helps Indian citizens discover public welfare schemes they may be eligible for, understand the criteria in plain language, and prepare to claim them. It is part of the ACE Builders Hackathon 2026, Problem Statement 5: Citizens and Public Services.

## Features

- A searchable, filterable, paginated scheme catalogue in `data/schemes.json`, including central and Uttar Pradesh records. The catalogue currently contains 19 records; several new entries are explicitly marked as needing eligibility-detail review.
- A conservative eligibility engine. Missing profile facts and unverified criteria remain unknown; a match is not an entitlement decision.
- Account registration/login with salted PBKDF2 password hashes and server-side, expiring SQLite sessions. Session cookies are HTTP-only and same-site.
- Database-backed profiles, saved schemes, application status, document checklists, notes, deadlines and in-app reminders.
- An API-driven responsive frontend, with optional English/Hindi browser speech recognition.
- The original FastAPI matching and application routes remain available. Existing SQLite application rows are preserved by additive schema migrations.

The SQLite database path defaults to `data/haqfinder.db`; set `HAQFINDER_DB` to use another file. Do not store Aadhaar, PAN, bank details, or other identity numbers in the profile.

### Scheme verification

The catalogue does not claim that every record's eligibility details have been verified. New portal records have empty eligibility, benefits and document fields until those details are checked. Their `verification_status`, `data_confidence`, `link_checked_at`, and `verification_note` fields distinguish a reachable official destination from verified scheme rules. `SOURCE_UNAVAILABLE` means a source could not be reached during its recorded check. Always confirm current rules with the official authority.

### Hero video

`static/community.mp4` is a locally stored, muted 12-second montage, with a local poster fallback at `static/community-poster.jpg`. The footage is from Pexels and is used under the [Pexels license](https://www.pexels.com/license/):

- [Atul Saini — farmer carrying a load in farmland](https://www.pexels.com/video/man-carrying-a-bag-while-walking-4684807/)
- [Samar L. — college campus in India](https://www.pexels.com/video/vibrant-college-campus-walkway-in-india-36878014/)
- [Mikhail Nilov — Indian woman working on a laptop](https://www.pexels.com/video/woman-using-a-laptop-9198479/)
- [Daily views — women vendors at a market stall](https://www.pexels.com/video/outdoor-market-stall-with-women-vendors-39916216/)

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
| `category` | string | Primary category. Additional filter categories may be listed in `categories`. |
| `description` | string | Short plain-language summary of the scheme. |
| `state` | string or null | `null` for central schemes, otherwise the state name. |
| `government_level` | string | `central` or `state`, when recorded. |
| `department` | string | Responsible department, when recorded. |
| `eligibility` | object | Structured conditions (see below). Keys are optional. |
| `benefits`, `eligibility_criteria` | lists | Officially sourced detail when available; empty when not yet reviewed. |
| `required_documents` | list of strings | Documents usually needed to apply. |
| `application_steps` | list of strings | Ordered steps to apply. |
| `deadline` | string or null | `YYYY-MM-DD`, or `null` if no fixed deadline is known. |
| `official_link`, `official_information_url`, `application_url` | strings | Official destinations. Application links fall back to the official information page when a separate application URL is not known. |
| `source_url` | string | Public page the criteria were summarized from. |
| `verification_status` | string | Review state from the ingestion pipeline; do not mark a record fully verified without checking its details. |
| `link_checked_at`, `last_verified` | date or null | Link check date and scheme-detail review date are kept separate. |
| `verification_note` | string | What was and was not checked. |

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
