# Portfolio Analyst — Design Principles

These principles were derived through extended analysis and represent 
closed architectural decisions. Do not re-derive or re-open them unless 
explicitly instructed.

## 1. Analyst / Allocator Firewall

The analyst and allocator are intentionally firewalled from each other.

- The **analyst** (Layer 2) receives only transcript text and returns 
  only a structured score: thesis health, recommendation, Type A/B 
  classification, suggested cap %, management credibility assessment. 
  The analyst never receives portfolio composition, position sizes, 
  price history, or data about any other ticker.

- The **allocator** (Layer 1) receives only scores and current portfolio 
  state — never transcripts. It applies mechanical rules (concentration 
  caps, tax-aware trim sequencing, account type priority) and produces 
  a specific action with a tax cost calculation.

- They communicate only through the structured score. This separation 
  is the primary structural defense against look-ahead bias in both 
  live use and historical backtesting.

## 2. Layer Ordering: 3 → 2 → 1

The operational sequence is find → classify → enforce, not the reverse.

- Layer 3 (Opportunity Scanner) identifies candidates
- Layer 2 (Analyst) scores them
- Layer 1 (Allocator) enforces mechanical rules

This ensures trim proceeds have a destination before the trim executes. 
Proportional redeployment into existing positions is the explicit 
failure mode being avoided.

## 3. Watchlist vs Portfolio Ticker Rules

- **Watchlist tickers**: maximum 6 transcripts. When a 7th is added, 
  the oldest is automatically discarded. Recommendation output: 
  buy / monitor / discard.

- **Portfolio tickers**: unlimited transcript history. Every quarter 
  adds a new entry. Recommendation output: hold / add / trim / exit 
  with specific measurable conditions.

- When a ticker is promoted from watchlist to portfolio, all existing 
  transcripts are preserved as historical context.

## 4. Backtest Integrity

The anonymization prompt (docs/EVALUATION_PROMPT.md) must be used 
for all historical backtesting to prevent Claude's training data from 
influencing transcript evaluations. Replace ticker symbols, executive 
names, geographies, and financials before submitting historical 
transcripts to the analyst.

## 5. Concentration Caps (Layer 1 Rules)

- Type A (single-driver thesis): hard cap 35% at peak conviction
- Type B (multi-driver platform): variable cap 40-60% based on 
  active driver count
- Tier 4 (above 30%): 48-hour waiting period before any hold 
  confirmation
- Tax-aware trim: always trim tax-advantaged accounts first
- Every trim recommendation includes explicit tax cost calculation

## 6. The Enough Number

Active management is only justified below $6M. The agent must include 
a module that checks current portfolio value against this threshold 
and asks whether continued active management is still in the 
investor's best interest. Target: reach $6M → move to S&P 500 ETF 
→ grow to $10M → shift to 60/40 passive allocation.

## 7. Blind Spot Countermeasures

Five blind spots are explicitly encoded in the evaluation prompt:

1. Sector thesis ≠ company thesis
2. Startup forgiveness does not apply to mature companies
3. Overconfidence — edge must be articulated in 1-2 specific sentences
4. Familiarity ≠ competence transfer across challenge types
5. Mitigation arguments inherit only the credibility of the 
   specific capability they depend on — not overall management 
   credibility

These are not reminders — they are structural checks built into 
every transcript evaluation.
