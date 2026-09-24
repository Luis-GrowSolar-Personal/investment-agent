# findings (append-only) - p6b-confound-and-concentration

- HYGIENE: the working tree carried the user's uncommitted rewrite of docs/handoffs/2026-09-24-state-of-play.{md,docx}. Per the standing rule it was backed up (scratchpad copy) and stashed (`git stash list`: "user-wip-2026-09-24-state-of-play (p6b-confound run)") so the clean-tree gate could be satisfied; it MUST be popped at the end of the run and is not part of any commit here.
- PREMISE FLAGS at read time:
  1. The prompt says 95 events are already re-scored by the noise arm and ~100 remain. It is the other way round: scores_noise_all16.jsonl holds **100** ALL16 events, so **95** remain to score (~$3.80 at the measured $0.0402/call, not ~$8).
  2. "Fresh v6 gave fewer Trims (18 vs 26)": that pair compares the N cell's mixed fed verdicts (100 fresh + 95 archived) with the 195 archived ones, so it is not a like-for-like model comparison. On the 100 noise events themselves: archived Add 65 / Hold 17 / Trim 18, fresh Add 54 / Hold 36 / Trim 10. The full 195-event comparison is computed in this run.
  3. "the wrap-up noted one archived event where v6 produced no direction": that was ETN 2025-05-02 (tune) and ACN 2022-03-17 (train), neither an ALL16 event. All 100 noise-arm ALL16 re-scores parsed. How the remaining 95 parse is recorded below.
  4. The 2026-09-24 state of play sections the prompt cites (5.1, 5.2, 5.3) exist only in the user's uncommitted rewrite (now stashed); the committed version still says "the end-to-end check, ~$16". Read from the stash diff; nothing depends on the difference.
