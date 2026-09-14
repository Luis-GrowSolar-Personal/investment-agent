# rule3-disposition — findings (append-only)

**Step 0c reproduction: MATCH.** R3_keep (control) reproduced to the cent at
$179,944.91. R3_remove (Stage C3's B2_disable_rule3) reproduced to the cent
at $189,362.81. No discrepancy. Proceeded past the gate.

**Premise correction (minor, does not change any figure):** the prompt names
`analysis/simulator/sweep_cadence_and_session_model.py` as the location of
the shortfall/funding logic. The file actually lives one directory up, at
`analysis/sweep_cadence_and_session_model.py` (not under `simulator/`). Line
numbers cited in the prompt (~866-877) match this file closely (confirmed
at lines 865-877 in the version at commit 5c0926c).

**Stage C3's displacement-selling prediction is CONFIRMED, not contradicted.**
R3-keep (status quo) generates 71 displacement-funded sells; R3-remove (guard
off) generates only 60. Status quo genuinely does more selling than removing
the guard, exactly as Stage C3's mechanism finding predicted.

**R3-enforce lands strictly between R3-keep and R3-remove in final value**
($184,459.65 vs. $179,944.91 and $189,362.81) and has by far the fewest
displacement-funded sells (37, vs. 60 and 71) and the fewest funding events
overall (75 vs. 97/98) -- consistent with genuinely blocking adds rather than
rerouting their funding source. 23 of the 195 events had their add-leg
target suppressed entirely under R3-enforce.

**R3-enforce also has the smallest drawdown of the three arms** (17.62% vs.
20.85% keep / 21.73% remove) -- consistent with Stage C3/D's general finding
that drawdown tracks how invested an arm is, not how well it calls
direction: R3-enforce carries the highest average cash share of the three
(28.73% vs. 26.02% keep / 22.76% remove).

**Leave-one-out: R3-enforce's effect (+$4,514.75) preserves sign in 16 of 16
worlds**, same full sign-preservation rate as R3-remove's restated Stage C3
result (also 16/16). AVGO is R3-enforce's biggest mover (dropping AVGO moves
the effect from $4,514.75 to $10,905.32, +$6,390.57) -- a different company
than R3-remove's biggest mover (ENVX, per Stage C3). Dropping SPWR leaves
R3-enforce's effect completely unchanged ($4,514.75 exactly), meaning no
Rule-3-triggering event in this population ever involves SPWR.

**Step 3 ceiling: Rule 3's ordering shifts under perfect calls.** Under
D-both (look-ahead ceiling, not a result): R3_keep=$263,073.65,
R3_remove=$265,386.41 (+$2,312.76 vs. keep), R3_enforce=$256,975.97
(-$6,097.68 vs. keep). Under real calls, enforce sat BETWEEN keep and
remove (+$4,514.75 vs. keep); under perfect calls, enforce falls BELOW
keep, while remove's edge over keep shrinks sharply from $9,417.91 to
$2,312.76.

**Step 4 timing: neither effect is concentrated in one quarter.**
R3-remove's $9,417.91 full-window edge accrues mostly in 2023-2024, not
2022 (cumulative by year: -$901 / $4,851 / $9,418); largest single quarter
is 2024 Q1 (+$2,757.76). R3-enforce's $4,514.75 edge is $3,337 / -$1,210 /
$4,515 across 2022/2023/2024; largest single quarter is 2024 Q2
(+$5,414.91). Neither is a one-quarter artifact.
