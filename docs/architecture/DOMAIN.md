# Portfolio Analyst — Investment Domain Definition
*Established: April 12, 2026*

This document defines the canonical investment domain (circle of competence)
for the Portfolio Analyst agent. It is a closed architectural decision.
All modules — Opportunity Scanner, intake evaluator, RADAR filters — must
reference this definition and never recommend or surface opportunities
outside it.

---

## Domain Tiers

### Tier 1 — Strong Edge
*Evaluate independently. High conviction warranted. Opportunity Scanner
actively monitors these areas for trends and new candidates.*

**Residential, C&I, and Small Utility Solar**
Day job since 2010. Former Enphase Energy. Deep network access with
visibility into many of the main players. Understands the full value
chain, market dynamics, and competitive landscape across residential,
commercial, and industrial/C&I segments. Can catch signals that
generalist analysts miss.

**Energy Storage**
Deep applied familiarity developed over several years as storage became
integral to solar systems. Understands the technology, its applications,
and the conditions under which a business proposition resonates if brought
to market successfully. Willing to engage at the technical level when
needed. Defense-adjacent storage companies (e.g. AMPX) are evaluated
under this domain, not under Defense.

**Semiconductors**
Approximately 20 years of industry experience through ~2010. Includes
work at a microprocessor IP company. Strong foundational knowledge of
fabless vs. fab dynamics, processor architecture, and IP licensing models.
A 15-year gap is acknowledged and explicitly flagged when evaluating
companies with post-2010 technology shifts. Core mental models transfer;
edge is real but requires more transcript discipline than Tier 1 solar
or storage.

---

### Tier 2 — Moderate Edge
*Can evaluate competently. Reactive sourcing only — Opportunity Scanner
does not proactively generate candidates here. Evaluation framework
carries more weight than domain knowledge.*

**IT / Software / Cloud**
Functional fluency. Can follow any earnings call from most software
companies. No structural informational advantage over a careful generalist
analyst. Positions in this space require stronger transcript evidence
to justify conviction.

**Crypto — Scoped**
General position: the technology is real and has legitimate applications,
but conviction requires demonstrated mass adoption with friction-free
utility — not speculative store-of-value narratives or unproven protocols.

Stablecoins are the current leading use case. Solana is the monitored
infrastructure bet, specifically for its potential as payments and
finance/credit/trading rails. The test: show millions of people using
it without friction.

In-scope: stablecoin issuers, payments infrastructure, custody and
settlement layer companies with measurable adoption metrics, BTC
(monitored position), SOL (infrastructure thesis).

Out of scope: pure speculative store-of-value plays, unproven L1/L2
protocols without a clear path to mass-adoption use cases.

---

### Removed — No Standalone Edge

**Defense Technology**
Procurement process familiarity is limited. Interest in this space
originated through AMPX, which is an energy storage company that
happens to serve defense applications. It is not genuine defense
technology expertise. Defense is not a standalone domain. Defense-
adjacent companies qualify only if their core thesis is grounded in
energy storage, semiconductors, or another Tier 1/2 domain.

---

## Opportunity Scanner Rules

1. Proactive trend monitoring and candidate surfacing: Tier 1 domains only.
2. Reactive evaluation (user-sourced candidates): all in-scope domains.
3. Crypto filter: surface only companies or assets with a demonstrable
   or near-demonstrable mass-adoption use case. Do not surface
   "next big blockchain" narratives.
4. Defense filter: only surface if the primary thesis lives in an
   in-scope domain (typically energy storage or semiconductors).
5. User may introduce candidates from outside the scanner — these
   still pass through the structured intake evaluation gate before
   entering the watchlist.

---

## Relationship to Other Documents

- `DESIGN_PRINCIPLES.md` — architectural rules for analyst/allocator
  firewall, layer ordering, concentration caps
- `EVALUATION_PROMPT.md` — structured evaluation used by Layer 2 analyst
- `BUILD_STATE.md` — current build progress and next steps
- `CLAUDE.md` — technical configuration and never-do rules
