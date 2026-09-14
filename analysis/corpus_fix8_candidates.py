"""
corpus_fix8_candidates.py -- corpus-fix-8, Step B candidate roster.

Drafted from general knowledge of large/mid-cap public companies circa
2020-12-31 -- NOT independently retrieved from a single live ranked table
this session, same caveat as the original corpus_construction_driver.py's
S1 selection (see its own comment: "ranks 11-40 not independently
re-verified against a single retrieved ranked table"). Every candidate
below is checked mechanically against A1/A2 (call availability) and A9
(price coverage) in corpus_fix8_driver.py -- the roster's job is only to
propose plausible, non-duplicate, sector/domain-tagged candidates; the
gates decide who survives.

No ticker below duplicates an existing corpus member (checked
programmatically in the driver against CORPUS_MANIFEST_V4.json).
"""

EXISTING_CORPUS_CHECK_NOTE = "driver cross-checks every ticker below against CORPUS_MANIFEST_V4.json before use"

# S1 -- approximate market-cap ranks ~41-80, Dec 2020, domain-agnostic
# (S1 is the large-cap bucket regardless of sector). 25 candidates, no
# random draw (deterministic list, per A10).
S1_CANDIDATES = [
    "UNH", "LLY", "ABBV", "MDT", "GILD", "AMGN", "DHR", "LOW", "SBUX",
    "BAC", "GS", "MS", "C", "SCHW", "HON", "UPS", "LMT", "RTX", "UNP",
    "EMR", "DIS", "TMUS", "CHTR", "DUK", "SO",
]

# S3 -- out of scope, 9 registered sectors (selection_working.json ->
# S3.reserves keys), 50 candidates total, <=6 per sector, weighted toward
# sectors thin/absent in today's 20-member S3 (materials/real_estate/
# media_telecom = 0; utilities = 1; healthcare_pharma = 3; the rest = 4).
S3_CANDIDATES = {
    "materials": ["DOW", "DD", "PPG", "ECL", "NEM", "FCX"],
    "real_estate": ["PLD", "AMT", "EQIX", "SPG", "PSA", "O"],
    "media_telecom": ["VIAC", "FOXA", "LYV", "NWSA", "IPG", "OMC"],
    "utilities": ["AEP", "EXC", "SRE", "D", "XEL", "ED"],
    "healthcare_pharma": ["CI", "ANTM", "CNC", "HCA", "ZTS", "BDX"],
    "consumer_staples": ["PG", "MO", "PM", "KHC", "STZ"],
    "financials": ["AXP", "BK", "TFC", "PNC", "COF"],
    "industrials": ["ITW", "ETN", "PH", "ROK", "CMI"],
    "energy": ["SLB", "OXY", "KMI", "WMB", "EOG"],
}

# S2 -- in DOMAIN.md (solar/storage/semiconductor/software-cloud/scoped
# crypto). 12 primary + 3 reserves for drop-and-replace.
S2_CANDIDATES = [
    "NOW", "WDAY", "TEAM", "SNOW",       # software/cloud
    "ON", "MPWR", "SWKS", "MCHP",        # semiconductors
    "SEDG", "CSIQ", "JKS", "MAXN",       # solar/storage
]
S2_RESERVES = ["MSTR", "SQ", "PYPL"]     # scoped-crypto / payments-adjacent

# S4 -- failures attempt. No new in-domain, public-by-2020-12-31, later-
# failed candidate was identified this round either (general knowledge
# search only -- not an exhaustive vendor/SEC search). Reported as a
# shortfall, per A10, rather than forced.
S4_CANDIDATES = []

# SPAC-era relaxed-rule candidates -- would qualify only under "public by
# 2021-12-31" instead of the registered 2020-12-31 test. Listed with call
# counts (fetched via vendor in this run) but NOT added -- Luis's decision.
SPAC_ERA_RELAXED_CANDIDATES = [
    {"ticker": "SUNL", "name": "Sunlight Financial Holdings",
     "domain_fit": "DOMAIN.md Tier 1 -- residential solar financing/loan origination platform",
     "public_since": "2021-07-09 (SPAC merger, Spartan Acquisition Corp II)",
     "failure": "Chapter 11, 2023-11-06"},
    {"ticker": "MVST", "name": "Microvast Holdings",
     "domain_fit": "DOMAIN.md Tier 1 -- lithium battery / energy storage manufacturer",
     "public_since": "2021-07-23 (SPAC merger, Tuscan Holdings)",
     "failure": "Not failed as of this run -- distressed/going-concern language in filings; "
                "included for completeness since it was flagged as a candidate, not because it "
                "meets S4's failure criterion yet"},
    {"ticker": "VLTA", "name": "Volta Industries",
     "domain_fit": "Borderline -- EV charging infrastructure, not squarely DOMAIN.md's storage "
                    "tier (grid/behind-the-meter storage systems), closer to the EV-OEM-adjacent "
                    "companies already excluded (Nikola/Fisker/Lordstown reasoning)",
     "public_since": "2021-08-26 (SPAC merger, Tortoise Acquisition Corp II)",
     "failure": "Acquired out of Chapter 11 by Shell, 2023-04"},
]
