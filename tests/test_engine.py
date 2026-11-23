"""Engine tests: sample citizen profiles run through the eligibility engine.

Scheme ids used (from data/schemes.json):
  pm-scholarship-scheme, pm-vidyalaxmi, nsp-post-matric-scholarship-sc-st-obc,
  pm-kisan, pm-fasal-bima-yojana, indira-gandhi-national-old-age-pension,
  pm-awas-yojana-gramin, ayushman-bharat-pm-jay, pm-mudra-yojana
"""

from app.engine import SCHEMES, match_schemes, merge_profile, parse_description

POSITIVE = {"likely_eligible", "possibly_eligible"}
VALID_STATUSES = {"likely_eligible", "possibly_eligible", "not_matched"}


def _run(text):
    """Parse a free-text description and return (profile, results keyed by scheme id)."""
    profile = merge_profile(parse_description(text), {})
    results = match_schemes(profile)
    return profile, {r["scheme_id"]: r for r in results}


def _status(by_id, scheme_id):
    """Status of a scheme, or None if the engine omitted it."""
    r = by_id.get(scheme_id)
    return r["status"] if r else None


def _assert_positive(by_id, scheme_id):
    assert _status(by_id, scheme_id) in POSITIVE, f"{scheme_id} expected positive, got {_status(by_id, scheme_id)}"


def _assert_not_matched(by_id, scheme_id):
    status = _status(by_id, scheme_id)
    assert status in (None, "not_matched"), f"{scheme_id} expected not_matched or absent, got {status}"


# 1. UP B.Tech student, farmer family, low income
def test_up_btech_student_farmer_family_gets_student_scholarship():
    _, by_id = _run(
        "Main Uttar Pradesh mein rehta hoon. Main B.Tech kar raha hoon. "
        "Mere father farmer hain. Hamari family income kam hai."
    )
    student_schemes = ["pm-scholarship-scheme", "pm-vidyalaxmi", "nsp-post-matric-scholarship-sc-st-obc"]
    assert any(_status(by_id, s) in POSITIVE for s in student_schemes), (
        "at least one student scholarship/loan scheme should be possibly_eligible or better"
    )


# 2. Rural 65-year-old BPL person
def test_rural_65_year_old_gets_old_age_pension():
    _, by_id = _run("Main gaon mein rehta hoon. Main gareeb hoon. Meri umar 65 saal hai.")
    _assert_positive(by_id, "indira-gandhi-national-old-age-pension")


# 3. Urban high-income salaried person: low-income schemes must not match
def test_urban_high_income_salaried_does_not_assume_pm_jay_income_cutoff():
    _, by_id = _run("Main Delhi mein urban area mein naukri karta hoon, salary 25 lakh saalana, age 30")
    for scheme_id in [
        "nsp-post-matric-scholarship-sc-st-obc",
        "pm-scholarship-scheme",
        "pm-vidyalaxmi",
        "pm-kisan",
        "pm-fasal-bima-yojana",
        "pm-awas-yojana-gramin",
    ]:
        _assert_not_matched(by_id, scheme_id)
    assert _status(by_id, "ayushman-bharat-pm-jay") == "possibly_eligible"


# 4. SC student from Bihar
def test_sc_student_from_bihar_gets_post_matric_scholarship():
    _, by_id = _run("Main Bihar se hoon, SC category mein hoon, 12th ke baad college mein padhta hoon")
    _assert_positive(by_id, "nsp-post-matric-scholarship-sc-st-obc")


# 5. Farmer in Punjab with income 1 lakh
def test_punjab_farmer_income_1_lakh_gets_pm_kisan_or_crop_insurance():
    _, by_id = _run("Punjab mein kisan hoon, income 1 lakh")
    assert any(_status(by_id, s) in POSITIVE for s in ["pm-kisan", "pm-fasal-bima-yojana"])


# 6. Cross-profile invariants
def test_status_values_and_reasons_are_valid_for_all_profiles():
    texts = [
        "Main Uttar Pradesh mein rehta hoon. Main B.Tech kar raha hoon. Mere father farmer hain. Hamari family income kam hai.",
        "Main gaon mein rehta hoon. Main gareeb hoon. Meri umar 65 saal hai.",
        "Main Delhi mein naukri karta hoon, salary 25 lakh saalana, age 30",
        "Main Bihar se hoon, SC category mein hoon, 12th ke baad college mein padhta hoon",
        "Punjab mein kisan hoon, income 1 lakh",
    ]
    for text in texts:
        _, by_id = _run(text)
        for r in by_id.values():
            assert r["status"] in VALID_STATUSES, f"unexpected status {r['status']!r} for {r['scheme_id']}"
            assert r["status"] != "guaranteed"
            assert (r.get("matched") or r.get("failed") or r.get("missing_info")), f"{r['scheme_id']} has no reasons"


def test_scheme_ids_in_results_exist_in_data():
    known = {s["id"] for s in SCHEMES}
    _, by_id = _run("Punjab mein kisan hoon, income 1 lakh")
    assert set(by_id) <= known


# parse_description extraction
def test_parse_age_from_mera_age_phrase():
    assert parse_description("mera age 65")["age"] == 65


def test_parse_income_2_lakh_is_200000():
    assert parse_description("income 2 lakh")["annual_income"] == 200000


def test_parse_up_abbreviation_maps_to_uttar_pradesh():
    assert parse_description("Main UP mein rehta hoon")["state"] == "Uttar Pradesh"



def test_hyphenated_age_phrase_is_parsed():
    assert parse_description("I am a 20-year-old college student from Uttar Pradesh")["age"] == 20
