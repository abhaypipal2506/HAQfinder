from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_catalogue_expanded_with_real_central_and_state_records():
    response = client.get("/api/schemes")
    assert response.status_code == 200
    schemes = response.json()
    assert len(schemes) == 19
    by_id = {scheme["id"]: scheme for scheme in schemes}
    assert by_id["mukhyamantri-kanya-sumangala-yojana"]["state"] == "Uttar Pradesh"
    assert by_id["mgnrega"]["government_level"] == "central"
    assert by_id["pm-ajay"]["verification_status"] == "SOURCE_UNAVAILABLE"


def test_category_search_and_pagination_use_catalogue_data():
    categories = set(client.get("/api/categories").json())
    assert {
        "education",
        "agriculture",
        "health",
        "employment",
        "housing",
        "pension",
        "finance",
        "women",
        "msme",
        "disability",
        "social_justice",
        "tribal_welfare",
        "food_security",
        "rural_development",
    } <= categories

    women = client.get("/api/schemes", params={"category": "women", "page_size": 100}).json()
    assert {item["id"] for item in women["items"]} >= {
        "pradhan-mantri-matru-vandana-yojana",
        "pradhan-mantri-ujjwala-yojana",
        "mukhyamantri-kanya-sumangala-yojana",
    }

    first = client.get("/api/schemes", params={"page": 1, "page_size": 5}).json()
    second = client.get("/api/schemes", params={"page": 2, "page_size": 5}).json()
    assert first["total"] == 19
    assert first["pages"] == 4
    assert len(first["items"]) == 5
    assert not {item["id"] for item in first["items"]} & {
        item["id"] for item in second["items"]
    }

    state_results = client.get(
        "/api/schemes", params={"state": "Uttar Pradesh", "page_size": 100}
    ).json()
    assert [item["id"] for item in state_results["items"]] == [
        "mukhyamantri-kanya-sumangala-yojana"
    ]


def test_unverified_scheme_needs_more_information_instead_of_assuming_eligible():
    response = client.post(
        "/api/match",
        json={"description": "I am looking for support for my family"},
    )
    assert response.status_code == 200
    result = next(
        item for item in response.json()["results"] if item["scheme_id"] == "pm-vishwakarma"
    )
    assert result["status"] == "possibly_eligible"
    assert result["manual_review"] is True
    assert "official_criteria_review" in result["missing_info"]
