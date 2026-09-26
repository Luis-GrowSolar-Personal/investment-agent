"""p5b_names.py -- prompts/P5-phase0b-link-sources.md Step 2a: the listed-company match list (SEC company_tickers.json + hand alias list). No network here;
company_tickers.json is read from the gitignored copy saved by p5b_filings.py."""
import re, json, csv
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
TICKERS = REPO / "analysis/data/evals/p5_phase0b/company_tickers.json"
ALIASES = REPO / "docs/peers/NAME_ALIASES.csv"
SUFFIX = {"inc", "corp", "corporation", "co", "company", "holdings", "holding", "ltd", "limited", "plc", "llc", "lp", "sa", "nv", "ag", "se", "the", "incorporated", "trust", "n.v", "s.a"}


def clean(title):
    words = re.sub(r"[.,]", " ", title).split()
    while words and words[-1].lower() in SUFFIX: words.pop()
    while words and words[0].lower() in SUFFIX: words.pop(0)
    return " ".join(words)


def build():
    """Returns (list of (name, ticker, source)), own-name map ticker -> set of names."""
    tk = json.loads(TICKERS.read_text())
    names = {}
    for v in tk.values():
        nm = clean(v["title"])
        if not nm: continue
        n_words = len(nm.split())
        if n_words >= 2 or len(nm) >= 7:
            for form in {nm.title(), nm}:               # "Nvidia" and the vendor's own casing
                names.setdefault(form, (v["ticker"], "sec"))
    for r in csv.DictReader(open(ALIASES)):
        names[r["alias"]] = (r["ticker"], "alias")
    return names


def matcher(names):
    # longest first, whole-word, case-sensitive (Title Case / vendor casing); avoids common-word noise better than case-insensitive
    ordered = sorted(names, key=len, reverse=True)
    return re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in ordered) + r")(?![A-Za-z0-9])")
