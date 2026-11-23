import pytest

from app import engine


STUDENT = {
    "state": "Uttar Pradesh",
    "age": 20,
    "annual_income": 90000,
    "occupation": "student",
    "education": "btech",
    "category": "OBC",
    "is_rural": True,
    "has_disability": False,
    "gender": "male",
}
FARMER_LAND = {"state": "Uttar Pradesh", "occupation": "farmer", "is_rural": True}
SENIOR_BPL = {"state": "Uttar Pradesh", "age": 65, "is_rural": True, "bpl": True}
SENIOR_NO_BPL = {"state": "Uttar Pradesh", "age": 65, "is_rural": True}
SECC_PERSON = {
    "state": "Uttar Pradesh",
    "annual_income": 200000,
    "occupation": "salaried",
    "is_rural": True,
}

IGNOAPS = "indira-gandhi-national-old-age-pension"


def _scheme(scheme_id):
    return next(s for s in engine.SCHEMES if s["id"] == scheme_id)


def _eval(profile, scheme_id):
    return engine.evaluate_scheme(profile, _scheme(scheme_id))


def _with_answers(profile, answers):
    p = dict(profile)
    p["special_answers"] = answers
    return p


def _condition(result, cond_id):
    return next(c for c in result["special_conditions"] if c["id"] == cond_id)


def test_pm_scholarship_unanswered_parent_condition_is_not_likely():
    result = _eval(STUDENT, "pm-scholarship-scheme")
    assert result["status"] == "possibly_eligible"
    assert "special:parent_ex_serviceman_or_capf" in result["missing_info"]


def test_pm_scholarship_parent_not_ex_serviceman_is_not_matched():
    profile = _with_answers(
        STUDENT,
        {"parent_ex_serviceman_or_capf": False, "admitted_recognised_institution": True},
    )
    result = _eval(profile, "pm-scholarship-scheme")
    assert result["status"] == "not_matched"
    criteria = [f["criterion"] for f in result["failed"]]
    assert "special:parent_ex_serviceman_or_capf" in criteria


def test_pm_scholarship_all_conditions_confirmed_is_likely():
    profile = _with_answers(
        STUDENT,
        {"parent_ex_serviceman_or_capf": True, "admitted_recognised_institution": True},
    )
    result = _eval(profile, "pm-scholarship-scheme")
    assert result["status"] == "likely_eligible"
    assert result["missing_info"] == []


def test_pm_scholarship_admission_unanswered_blocks_likely():
    profile = _with_answers(STUDENT, {"parent_ex_serviceman_or_capf": True})
    result = _eval(profile, "pm-scholarship-scheme")
    assert result["status"] == "possibly_eligible"
    assert "special:admitted_recognised_institution" in result["missing_info"]


def test_pm_kisan_land_unanswered_is_possibly():
    result = _eval(FARMER_LAND, "pm-kisan")
    assert result["status"] == "possibly_eligible"
    assert "special:owns_agricultural_land" in result["missing_info"]


def test_pm_kisan_land_owned_is_likely():
    profile = _with_answers(FARMER_LAND, {"owns_agricultural_land": True})
    result = _eval(profile, "pm-kisan")
    assert result["status"] == "likely_eligible"


def test_pm_kisan_no_land_is_not_matched():
    profile = _with_answers(FARMER_LAND, {"owns_agricultural_land": False})
    result = _eval(profile, "pm-kisan")
    assert result["status"] == "not_matched"


def test_ignoaps_bpl_unanswered_is_possibly():
    result = _eval(SENIOR_NO_BPL, IGNOAPS)
    assert result["status"] == "possibly_eligible"
    assert "special:below_poverty_line" in result["missing_info"]


def test_ignoaps_self_reported_bpl_is_labelled():
    result = _eval(SENIOR_BPL, IGNOAPS)
    cond = _condition(result, "below_poverty_line")
    assert cond["state"] == "MATCH"
    assert "self-reported" in cond["reason"]


def test_ignoaps_bpl_false_is_not_matched():
    profile = _with_answers(SENIOR_NO_BPL, {"below_poverty_line": False})
    result = _eval(profile, IGNOAPS)
    assert result["status"] == "not_matched"


def test_pm_jay_secc_unanswered_is_possibly():
    result = _eval(SECC_PERSON, "ayushman-bharat-pm-jay")
    assert result["status"] == "possibly_eligible"
    assert "special:secc_or_pmjay_listed" in result["missing_info"]


def test_pm_jay_secc_false_is_not_matched():
    profile = _with_answers(SECC_PERSON, {"secc_or_pmjay_listed": False})
    result = _eval(profile, "ayushman-bharat-pm-jay")
    assert result["status"] == "not_matched"


def test_special_answers_never_turn_unknown_into_match():
    schemes_with_conditions = [s for s in engine.SCHEMES if s.get("special_conditions")]
    assert schemes_with_conditions, "expected at least one scheme with special_conditions"
    for scheme in schemes_with_conditions:
        result = engine.evaluate_scheme(STUDENT, scheme)
        for cond in result["special_conditions"]:
            if STUDENT.get("bpl") is True:
                continue
            assert cond["state"] != "MATCH", (scheme["id"], cond["id"])
            assert cond["state"] == "UNKNOWN", (scheme["id"], cond["id"])


def test_every_special_condition_has_required_fields():
    required_keys = {"id", "label", "question", "required", "source_url", "verification_status"}
    for scheme in engine.SCHEMES:
        for cond in scheme.get("special_conditions", []):
            assert required_keys.issubset(cond.keys()), (scheme["id"], cond.get("id"))
            assert cond["verification_status"] == "UNVERIFIED_MANUAL_REVIEW_REQUIRED", (
                scheme["id"],
                cond["id"],
            )


def test_result_has_manual_review_flag():
    result = _eval(STUDENT, "pm-scholarship-scheme")
    assert isinstance(result["manual_review"], bool)
    assert result["manual_review"] is True
