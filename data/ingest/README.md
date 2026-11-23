# Ingesting scheme data

This folder holds JSON files of scheme records that are imported into HAQfinder's
database through the ingestion pipeline (`app/ingest/`). Run every command from the
project root.

## Commands

```
python -m app.ingest.cli seed                          # load data/schemes.json (existing hand-entered set)
python -m app.ingest.cli import data/ingest/<name>.json  # import one batch from this folder
python -m app.ingest.cli links                         # check official URLs of live schemes (NETWORK)
python -m app.ingest.cli status                        # live scheme count and last 10 sync log rows
```

## Import rules

- **All-or-nothing.** If any record in a file fails validation, nothing from that file is
  written. The report lists every rejected record (index, scheme_id, errors).
- **Update, not replace.** An import upserts by `scheme_id`. Records that are not in the
  file are kept. Nothing is deleted by an import.
- **Duplicates are reported, not merged.** Two records with the same `source_url`, or with
  very similar names, are listed in the report. A `scheme_id` that already exists from a
  different source is also listed. A human decides what to do.
- **Warnings do not block an import.** Examples: `age_min` greater than `age_max`, a
  central scheme with a state set, or a deadline that has passed.
- **Sync log.** Every import writes one row to `sync_log` with status `ok` or `failed`.

## File format

A file is a JSON object:

```json
{
  "source_id": "pmjay",
  "schemes": [ { ...record... }, { ...record... } ]
}
```

If `source_id` is missing, the filename without `.json` is used. A bare JSON list of
records is also accepted. The file must be inside `data/ingest/`.

## Record fields

Fields are produced by `app/ingest/normalize.py`. Unknown or missing fields become `null`
(or `[]`, `{}`, `""` for lists, objects and notes). Nothing is invented: a missing deadline
stays `null`.

| Field | Type | Notes |
|---|---|---|
| `scheme_id` | string | Required. Derived from the name by slugifying when omitted. |
| `scheme_name` | string | Required. |
| `description` | string or null | |
| `government_level` | `central` / `state` / `unknown` | Anything else becomes `unknown`. |
| `state` | string or null | Required to be null for central schemes. |
| `department` | string or null | |
| `category` | string | One of: education, agriculture, health, housing, pension, finance, employment, women, disability, entrepreneurship, social_security, social_justice, tribal_welfare, food_security, rural_development, msme, other. Unknown values become `other`. |
| `beneficiaries` | list | |
| `eligibility` | object | Structured criteria, e.g. `{"age_min": 18, "income_max": 300000}`. |
| `eligibility_criteria` | list of strings | Human-readable criteria. |
| `benefits` | list | |
| `required_documents` | list | |
| `application_steps` | list | |
| `deadline` | `YYYY-MM-DD` or null | Must be a real calendar date. |
| `official_information_url` | https URL or null | |
| `application_url` | https URL or null | |
| `source_id` | string | Required. Set to the file's `source_id` when missing. |
| `source_name` | string or null | Human-readable name of the source. |
| `source_url` | https URL | Required. Must be on an allowed official domain (see `app/ingest/sources.py`). |
| `source_published_date` | `YYYY-MM-DD` or null | |
| `verification_status` | one of the 5 values below | Set by a human reviewer. Defaults to `AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED`. |
| `data_confidence` | string | Default `low`. |
| `notes` | string | |

Set by the pipeline, not by you: `last_checked_at`. The fields `scheme_name_local`
and `last_verified_at` are always `null` on import.

Validation rejects a record when it has no `scheme_id`, no `scheme_name`, no `source_id`,
no `source_url`, a `source_url` that is not https on an allowed domain, an invalid
`verification_status`, a malformed `deadline`, a non-integer or negative `age_min` /
`age_max` / `income_max`, or a non-https `official_information_url` / `application_url`.

## Adding a new scheme batch

1. Create `data/ingest/<name>.json` with `source_id` and a `schemes` array.
2. Fill in each record from the official page. Copy `source_url` from the page you read.
3. Set `verification_status` honestly (see below).
4. Run `python -m app.ingest.cli import data/ingest/<name>.json`.
5. Read the report. If `committed: False`, fix the listed records and run it again.
6. Run `python -m app.ingest.cli links` to check the URLs, then `status` to confirm the log.

## Verification statuses

A human reviewer sets `verification_status`. The importer does not decide it.

| Status | Meaning |
|---|---|
| `VERIFIED_FROM_OFFICIAL_SOURCE` | A reviewer opened the official page and confirmed the criteria, deadline and links against it. |
| `OFFICIAL_SOURCE_FOUND_DETAILS_REQUIRE_REVIEW` | The official page was found, but some details (criteria, dates, documents) still need a reviewer. |
| `AUTOMATICALLY_RETRIEVED_NOT_FULLY_VERIFIED` | The data came from an automated or hand-entry step and has not been checked against the official page. This is the default. |
| `SOURCE_UNAVAILABLE` | The official source could not be reached, or the scheme page no longer exists. The record cannot be checked. |
| `OUTDATED_NEEDS_REVIEW` | A record that was verified before may now be stale, for example because its deadline passed or the page changed. |

Do not set `VERIFIED_FROM_OFFICIAL_SOURCE` unless someone has checked the record.

## The `links` command

`links` performs real network requests to each official URL of every live scheme. Each
URL gets one verdict: `OK`, `BROKEN`, `REDIRECT_OFFSITE`, `UNABLE_TO_VERIFY`, or
`NOT_ALLOWED_DOMAIN`. It respects `robots.txt` and waits at least 2 seconds between
requests to the same host. A failed or blocked request is reported as
`UNABLE_TO_VERIFY`, not `BROKEN`. A link is only `BROKEN` when the server answers with a
4xx or 5xx status other than 401, 403 or 429.

## Hosting note

Render's free instance filesystem is not persistent across redeploys. Records imported
on the server, and the sync log, can be lost when the service is redeployed or restarted.
Keep the JSON files in this folder in git and re-run the import after a redeploy.
