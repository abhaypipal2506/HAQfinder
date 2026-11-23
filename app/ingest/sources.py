"""Registry of official government sources and URL allow-list checks."""

from urllib.parse import urlparse

SOURCES = [
    {
        "source_id": "myscheme",
        "name": "MyScheme",
        "base_url": "https://www.myscheme.gov.in",
        "domain": "www.myscheme.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": True,
        "notes": "Scheme pages render client-side; not auto-scraped; sitemap only",
    },
    {
        "source_id": "scholarships",
        "name": "National Scholarship Portal (scholarships.gov.in)",
        "base_url": "https://scholarships.gov.in",
        "domain": "scholarships.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "",
    },
    {
        "source_id": "nsp",
        "name": "National Scholarship Portal (nsp.gov.in)",
        "base_url": "https://nsp.gov.in",
        "domain": "nsp.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "",
    },
    {
        "source_id": "pmkisan",
        "name": "PM-KISAN",
        "base_url": "https://pmkisan.gov.in",
        "domain": "pmkisan.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "",
    },
    {
        "source_id": "pmfby",
        "name": "Pradhan Mantri Fasal Bima Yojana",
        "base_url": "https://pmfby.gov.in",
        "domain": "pmfby.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "",
    },
    {
        "source_id": "mudra",
        "name": "MUDRA (Mudra Yojana)",
        "base_url": "https://www.mudra.org.in",
        "domain": "www.mudra.org.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "",
    },
    {
        "source_id": "pmjay",
        "name": "Ayushman Bharat PM-JAY",
        "base_url": "https://pmjay.gov.in",
        "domain": "pmjay.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "timed out during discovery",
    },
    {
        "source_id": "nha_pmjay",
        "name": "National Health Authority PM-JAY",
        "base_url": "https://nha.gov.in/PM-JAY",
        "domain": "nha.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official information page checked; scheme details still need review",
    },
    {
        "source_id": "nsap",
        "name": "National Social Assistance Programme",
        "base_url": "https://nsap.nic.in/",
        "domain": "nsap.nic.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination was unavailable during the last link check",
    },
    {
        "source_id": "pmayg",
        "name": "Pradhan Mantri Awaas Yojana-Gramin",
        "base_url": "https://pmayg.dord.gov.in/",
        "domain": "dord.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "uponline",
        "name": "UP Online",
        "base_url": "https://www.uponline.in",
        "domain": "www.uponline.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Uttar Pradesh government portal aggregator; verify each scheme on the department site",
    },
    {
        "source_id": "mgnrega",
        "name": "MGNREGA official portal",
        "base_url": "https://nrega.nic.in/",
        "domain": "nrega.nic.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "pmmvy",
        "name": "Pradhan Mantri Matru Vandana Yojana",
        "base_url": "https://pmmvy.wcd.gov.in/",
        "domain": "wcd.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "nfsa",
        "name": "National Food Security Act portal",
        "base_url": "https://nfsa.gov.in/portal/nfsa-act",
        "domain": "nfsa.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; state entitlements need manual verification",
    },
    {
        "source_id": "tribal",
        "name": "Ministry of Tribal Affairs scholarship portal",
        "base_url": "https://tribal.nic.in/Scholarship.aspx",
        "domain": "tribal.nic.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "depwd",
        "name": "Department of Empowerment of Persons with Disabilities",
        "base_url": "https://depwd.gov.in/en/schemes/",
        "domain": "depwd.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "pmvishwakarma",
        "name": "PM Vishwakarma",
        "base_url": "https://pmvishwakarma.gov.in/",
        "domain": "pmvishwakarma.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "pmuy",
        "name": "Pradhan Mantri Ujjwala Yojana",
        "base_url": "https://www.pmuy.gov.in/",
        "domain": "pmuy.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "up_welfare",
        "name": "Uttar Pradesh Women Welfare",
        "base_url": "https://mksy.up.gov.in/women_welfare/",
        "domain": "up.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official state destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "pmjdy",
        "name": "Pradhan Mantri Jan-Dhan Yojana",
        "base_url": "https://pmjdy.gov.in/",
        "domain": "pmjdy.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; scheme details still need manual verification",
    },
    {
        "source_id": "pmvidyalaxmi",
        "name": "PM Vidyalaxmi",
        "base_url": "https://pmvidyalaxmi.co.in/",
        "domain": "pmvidyalaxmi.co.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Official destination checked; eligibility details still need manual verification",
    },
    {
        "source_id": "socialjustice",
        "name": "Ministry of Social Justice and Empowerment",
        "base_url": "https://socialjustice.gov.in/schemes/",
        "domain": "socialjustice.gov.in",
        "source_type": "official_portal",
        "robots_policy_checked": False,
        "notes": "Unavailable during the last link check; re-verify before relying on records",
    },
]

ALLOWED_DOMAINS = {s["domain"] for s in SOURCES}


def is_allowed_url(url: str) -> bool:
    """Return True only for https URLs whose host is an allowed domain or a subdomain of one."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False
