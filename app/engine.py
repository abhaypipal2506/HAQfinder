"""Pure-Python HAQfinder eligibility engine (no web framework imports)."""
import json
import re

ORDER = {"likely_eligible": 0, "possibly_eligible": 1, "not_matched": 2}

EDU_RANK = {
    "10th": 1, "class 10 pass": 1,
    "12th": 2, "class 12 pass": 2,
    "graduate": 3, "btech": 3,
    "post-graduate": 4, "postgraduate": 4,
}

STATE_ALIASES = {
    "Uttar Pradesh": ["uttar pradesh", "up"],
    "Bihar": ["bihar"],
    "Punjab": ["punjab"],
    "Maharashtra": ["maharashtra"],
    "Rajasthan": ["rajasthan"],
    "Madhya Pradesh": ["madhya pradesh", "mp"],
    "Delhi": ["delhi", "new delhi"],
    "Karnataka": ["karnataka"],
    "Tamil Nadu": ["tamil nadu", "tn"],
    "Gujarat": ["gujarat"],
    "West Bengal": ["west bengal", "bengal", "wb"],
    "Haryana": ["haryana"],
    "Odisha": ["odisha", "orissa"],
    "Kerala": ["kerala"],
    "Telangana": ["telangana"],
    "Andhra Pradesh": ["andhra pradesh", "andhra"],
    "Jharkhand": ["jharkhand"],
    "Chhattisgarh": ["chhattisgarh", "chattisgarh"],
    "Uttarakhand": ["uttarakhand", "uttaranchal"],
    "Himachal Pradesh": ["himachal pradesh", "himachal"],
    "Assam": ["assam"],
    "Goa": ["goa"],
}

OCCUPATION_RULES = [
    ("farmer", r"kisan|kisaan|farmer|kheti|farming"),
    ("student", r"student|chhatra|padhai|b\.?\s?tech|college"),
    ("unemployed", r"unemployed|berozgar|bekaar|jobless"),
    ("salaried", r"naukri|salaried|job|salary"),
    ("self-employed", r"self[- ]employed|business|shopkeeper|dukaan|entrepreneur|artisan"),
    ("senior", r"senior citizen|retired|pensioner|buzurg"),
]


def load_schemes(path="data/schemes.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["schemes"]


SCHEMES = load_schemes()


def reload_schemes():
    SCHEMES[:] = load_schemes()
    return SCHEMES


def _has(text, pattern):
    return re.search(r"\b(?:" + pattern + r")\b", text) is not None


def _find_state(text):
    best, best_pos = None, len(text) + 1
    for canonical, aliases in STATE_ALIASES.items():
        for alias in aliases:
            m = re.search(r"\b" + re.escape(alias) + r"\b", text)
            if m and m.start() < best_pos:
                best, best_pos = canonical, m.start()
    return best


def _find_income(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?)\b", text)
    if m:
        multiplier = 10000000 if m.group(2).startswith("crore") else 100000
        return int(float(m.group(1)) * multiplier)
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:rs\.?|inr|₹)?\s*(?:per month|a month|monthly|per mahine|per mahina|mahine|mahina|/month|/mahina)", text)
    if m:
        return int(float(m.group(1).replace(",", "")) * 12)
    m = re.search(r"(?:income|salary|kamai|kamaai|vetan|earn\w*)\D{0,20}?(\d[\d,]*)", text)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


PARENT_RE = r"father|mother|papa|mummy|mom|dad|maa|mata|pita|pitaji|parent|parents|guardian"
MOTHER_RE = r"mother|mom|mummy|maa|mata"
FATHER_RE = r"father|papa|dad|pita|pitaji"


def _split_applicant_and_family(t):
    applicant, family = [], {}
    for sentence in re.split(r"[!?;\n]|\.(?=\s|$)", t):
        sentence = sentence.strip()
        if not sentence:
            continue
        if _has(sentence, PARENT_RE):
            if _has(sentence, MOTHER_RE):
                relation = "mother"
            elif _has(sentence, FATHER_RE):
                relation = "father"
            else:
                relation = "parent"
            for name, pattern in OCCUPATION_RULES:
                if _has(sentence, pattern):
                    family.setdefault(relation, name)
                    break
        else:
            applicant.append(sentence)
    return " . ".join(applicant), family


def parse_description(text):
    t = (text or "").lower()
    applicant_t, family_occupations = _split_applicant_and_family(t)

    age = None
    m = re.search(r"\bage\s*(?:is|:)?\s*(\d{1,3})\b", applicant_t) or re.search(
        r"\b(\d{1,3})[\s-]*(?:saal|years?|yrs?|yr)\b", applicant_t)
    if m:
        age = int(m.group(1))

    occupation = None
    for name, pattern in OCCUPATION_RULES:
        if _has(applicant_t, pattern):
            occupation = name
            break

    if _has(applicant_t, r"post[- ]?graduate|mba|mtech|m\.?tech|masters"):
        education = "postgraduate"
    elif _has(applicant_t, r"b\.?\s?tech"):
        education = "btech"
    elif _has(applicant_t, r"graduate|graduation|bachelor|bsc|b\.sc|bcom|b\.com"):
        education = "graduate"
    elif _has(applicant_t, r"12th|12 th|class 12|class xii|intermediate|12 pass"):
        education = "12th"
    elif _has(applicant_t, r"10th|10 th|class 10|matric"):
        education = "10th"
    else:
        education = None

    if _has(applicant_t, r"ews"):
        category = "EWS"
    elif _has(applicant_t, r"obc"):
        category = "OBC"
    elif _has(applicant_t, r"sc"):
        category = "SC"
    elif _has(applicant_t, r"st"):
        category = "ST"
    elif _has(applicant_t, r"minority|alpsankhyak|muslim|christian|sikh|jain|buddhist"):
        category = "Minority"
    elif _has(applicant_t, r"general|unreserved|open category"):
        category = "General"
    else:
        category = None

    if _has(applicant_t, r"rural|gaon|village|dehat|gramin"):
        is_rural = True
    elif _has(applicant_t, r"urban|shahar|city"):
        is_rural = False
    else:
        is_rural = None

    has_disability = True if _has(applicant_t, r"disability|disabled|viklang|divyang|handicap") else None

    if _has(applicant_t, r"female|ladki|ladkiyan|mahila|woman|women|aurat|girl"):
        gender = "female"
    elif _has(applicant_t, r"male|ladka|man|boy|aadmi|purush"):
        gender = "male"
    else:
        gender = None

    income_hint = "low" if _has(t, r"kam income|low income|gareeb|bpl") else None

    return {
        "state": _find_state(t),
        "age": age,
        "annual_income": _find_income(t),
        "income_hint": income_hint,
        "occupation": occupation,
        "education": education,
        "category": category,
        "is_rural": is_rural,
        "has_disability": has_disability,
        "gender": gender,
        "family_occupations": family_occupations,
        "bpl": True if _has(t, r"bpl|below poverty line|garib rekha") else None,
    }



def merge_profile(parsed, overrides):
    merged = dict(parsed)
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return merged


def evaluate_scheme(profile, scheme):
    elig = scheme.get("eligibility", {})
    matched, failed, missing = [], [], []

    def ok(criterion, reason):
        matched.append({"criterion": criterion, "reason": reason})

    def bad(criterion, reason):
        failed.append({"criterion": criterion, "reason": reason})

    def need(field):
        if field not in missing:
            missing.append(field)

    for criterion, wanted in (("state", scheme.get("state")), ("residence_state", elig.get("residence_state"))):
        if wanted is None:
            continue
        mine = profile.get("state")
        if mine is None:
            need("state")
        elif mine == wanted:
            ok(criterion, f"You live in {mine}, which this scheme covers")
        else:
            bad(criterion, f"This scheme is only for {wanted} residents, but you live in {mine}")

    if "income_max" in elig:
        limit = elig["income_max"]
        income = profile.get("annual_income")
        if income is None:
            if profile.get("income_hint") == "low":
                ok("income_max", "Your description suggests low income")
            else:
                need("annual_income")
        elif income <= limit:
            ok("income_max", f"Annual income of Rs {income:,} is within the limit of Rs {limit:,}")
        else:
            bad("income_max", f"Annual income of Rs {income:,} is above the limit of Rs {limit:,}")

    if "age_min" in elig:
        age = profile.get("age")
        if age is None:
            need("age")
        elif age >= elig["age_min"]:
            ok("age_min", f"Your age {age} meets the minimum age of {elig['age_min']}")
        else:
            bad("age_min", f"Your age {age} is below the minimum age of {elig['age_min']}")

    if "age_max" in elig:
        age = profile.get("age")
        if age is None:
            need("age")
        elif age <= elig["age_max"]:
            ok("age_max", f"Your age {age} is within the maximum age of {elig['age_max']}")
        else:
            bad("age_max", f"Your age {age} is above the maximum age of {elig['age_max']}")

    if "occupation_in" in elig:
        occ = profile.get("occupation")
        allowed = [x.lower() for x in elig["occupation_in"]]
        if occ is None:
            need("occupation")
        elif occ.lower() in allowed:
            ok("occupation_in", f"Your occupation ({occ}) is one this scheme covers")
        else:
            bad("occupation_in", f"This scheme is for {', '.join(elig['occupation_in'])}, but your occupation is {occ}")

    if "education_in" in elig:
        edu = profile.get("education")
        levels = [EDU_RANK[x.lower()] for x in elig["education_in"] if x.lower() in EDU_RANK]
        minimum = min(levels) if levels else 0
        if edu is None:
            need("education")
        else:
            rank = EDU_RANK.get(edu.lower())
            if rank is not None and rank >= minimum:
                ok("education_in", f"Your education ({edu}) meets the requirement")
            else:
                bad("education_in", f"This scheme needs at least {', '.join(elig['education_in'])}, but your education is {edu}")

    if "category_in" in elig:
        cat = profile.get("category")
        allowed = [x.lower() for x in elig["category_in"]]
        if cat is None:
            need("category")
        elif cat.lower() in allowed:
            ok("category_in", f"Your category ({cat}) is covered by this scheme")
        else:
            bad("category_in", f"This scheme is for {', '.join(elig['category_in'])}, but your category is {cat}")

    if "is_rural" in elig:
        rural = profile.get("is_rural")
        want = "rural" if elig["is_rural"] else "urban"
        if rural is None:
            need("is_rural")
        elif rural == elig["is_rural"]:
            ok("is_rural", f"This scheme is for {want} residents, which matches you")
        else:
            bad("is_rural", f"This scheme is for {want} residents only")

    if "has_disability" in elig:
        dis = profile.get("has_disability")
        if dis is None:
            need("has_disability")
        elif dis == elig["has_disability"]:
            ok("has_disability", "Your disability status matches this scheme")
        else:
            bad("has_disability", "Your disability status does not match this scheme")

    if "gender_in" in elig:
        gender = profile.get("gender")
        allowed = [x.lower() for x in elig["gender_in"]]
        if gender is None:
            need("gender")
        elif gender.lower() in allowed:
            ok("gender_in", f"Your gender ({gender}) is covered by this scheme")
        else:
            bad("gender_in", f"This scheme is for {', '.join(elig['gender_in'])}, but your gender is {gender}")

    if scheme.get("verification_status") and scheme["verification_status"] != "VERIFIED_FROM_OFFICIAL_SOURCE":
        need("official_criteria_review")

    # Special conditions: each is MATCH (answered yes), MISMATCH (answered no)
    # or UNKNOWN (not answered). Only UNKNOWN is never silently treated as a match.
    answers = profile.get("special_answers") or {}
    unknown_conditions = []
    special_conditions = []
    for cond in scheme.get("special_conditions", []):
        cid = cond["id"]
        label = cond.get("label", cid)
        answer = answers.get(cid)
        if answer is None and cid == "below_poverty_line" and profile.get("bpl") is True:
            answer = True
            reason = "BPL status is self-reported and still needs official verification"
            ok(f"special:{cid}", reason)
            special_conditions.append({**cond, "state": "MATCH", "reason": reason})
        elif answer is None:
            unknown = {"id": cid, "label": label, "question": cond.get("question", label)}
            unknown_conditions.append(unknown)
            missing.append(f"special:{cid}")
            special_conditions.append({**cond, "state": "UNKNOWN", "reason": None})
        elif answer:
            reason = f"Self-reported: {label}; verify with the scheme authority"
            ok(f"special:{cid}", reason)
            special_conditions.append({**cond, "state": "MATCH", "reason": reason})
        elif cond.get("required", True):
            reason = f"Self-reported condition not met: {label}"
            bad(f"special:{cid}", reason)
            special_conditions.append({**cond, "state": "MISMATCH", "reason": reason})
        else:
            special_conditions.append({**cond, "state": "MISMATCH", "reason": None})

    if failed:
        status = "not_matched"
    elif missing or unknown_conditions:
        status = "possibly_eligible"
    else:
        status = "likely_eligible"

    return {
        "scheme_id": scheme["id"],
        "name": scheme["name"],
        "status": status,
        "matched": matched,
        "failed": failed,
        "missing_info": missing,
        "unknown_conditions": unknown_conditions,
        "special_conditions": special_conditions,
        "manual_review": (
            scheme.get("verification_status") != "VERIFIED_FROM_OFFICIAL_SOURCE"
            if scheme.get("verification_status")
            else any(
                cond.get("verification_status") != "VERIFIED_FROM_OFFICIAL_SOURCE"
                for cond in scheme.get("special_conditions", [])
            )
        ),
    }


def match_schemes(profile):
    results = [evaluate_scheme(profile, scheme) for scheme in SCHEMES]
    return sorted(results, key=lambda r: ORDER[r["status"]])


QUESTIONS = {
    "official_criteria_review": "The official eligibility rules for this scheme need to be reviewed before a reliable match can be assessed.",
    "annual_income": "What is your annual family income in INR?",
    "age": "What is your age?",
    "occupation": "What is your current occupation (farmer, student, salaried, self-employed, unemployed or senior)?",
    "education": "What is your highest education level (10th, 12th, graduate or post-graduate)?",
    "category": "Which social category do you belong to (SC, ST, OBC, EWS, General or Minority)?",
    "state": "Which state do you live in?",
    "is_rural": "Do you live in a rural or an urban area?",
    "has_disability": "Do you have a disability?",
    "gender": "What is your gender?",
}


def missing_questions(results):
    questions = []
    for result in results:
        if result["status"] != "possibly_eligible":
            continue
        for field in result["missing_info"]:
            question = QUESTIONS.get(field, f"Please provide your {field.replace('_', ' ')}.")
            if question not in questions:
                questions.append(question)
        for cond in result.get("unknown_conditions", []):
            if cond["question"] not in questions:
                questions.append(cond["question"])
    return questions
