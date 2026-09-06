## Step 0 -- draw (2026-09-06T21:09:42.783763+00:00)

207 targets: 200 reused from `analysis/data/run_state/av-fidelity-benchmark-2-stratified/progress.json` → `drawn` (seed 20260905), plus 7 pilot controls. By tier: {'small_micro': 59, 'mid': 44, 'large': 51, 'megacap': 53}. No vendor calls made.

**Company-level coverage miss**: GOOGL (tier megacap) absent from symbols-v2.txt (2026-09-06T21:09:51.646211+00:00)

**Event-level coverage miss**: SPWR call 2025-04-30 (bucket label 2025Q1, tier small_micro, transcript id 32) -- no vendor event within ±3 days (2026-09-06T21:10:52.872185+00:00)

**Event-level coverage miss**: RUN call 2021-08-05 (bucket label 2021Q2, tier small_micro, transcript id 374) -- no vendor event within ±3 days (2026-09-06T21:10:52.873928+00:00)

**Event-level coverage miss**: AVGO call 2022-05-26 (bucket label 2022Q1, tier large, transcript id 263) -- no vendor event within ±3 days (2026-09-06T21:10:52.875240+00:00)

**Event-level coverage miss**: GOOGL call 2021-07-27 (bucket label 2021Q2, tier megacap, transcript id 308) -- no vendor event within ±3 days (2026-09-06T21:10:52.875909+00:00)

**Event-level coverage miss**: GOOGL call 2023-02-02 (bucket label 2022Q4, tier megacap, transcript id 302) -- no vendor event within ±3 days (2026-09-06T21:10:52.875974+00:00)

**Event-level coverage miss**: GOOGL call 2023-04-25 (bucket label 2023Q1, tier megacap, transcript id 301) -- no vendor event within ±3 days (2026-09-06T21:10:52.876033+00:00)

**Event-level coverage miss**: GOOGL call 2023-10-24 (bucket label 2023Q3, tier megacap, transcript id 296) -- no vendor event within ±3 days (2026-09-06T21:10:52.876088+00:00)

**Event-level coverage miss**: GOOGL call 2024-07-23 (bucket label 2024Q2, tier megacap, transcript id 299) -- no vendor event within ±3 days (2026-09-06T21:10:52.876139+00:00)

**Event-level coverage miss**: GOOGL call 2025-04-24 (bucket label 2025Q1, tier megacap, transcript id 113) -- no vendor event within ±3 days (2026-09-06T21:10:52.876188+00:00)

**Event-level coverage miss**: GOOGL call 2025-10-29 (bucket label 2025Q3, tier megacap, transcript id 108) -- no vendor event within ±3 days (2026-09-06T21:10:52.876237+00:00)

**Event-level coverage miss**: GOOGL call 2026-04-29 (bucket label 2026Q1, tier megacap, transcript id 145) -- no vendor event within ±3 days (2026-09-06T21:10:52.876293+00:00)

**Event-level coverage miss**: GOOGL call 2026-07-22 (bucket label 2026Q2, tier megacap, transcript id 757) -- no vendor event within ±3 days (2026-09-06T21:10:52.876343+00:00)

## Label diagnostic (Step 1b)

Vendor (year, quarter) vs call-month bucket label disagreed on 68/195 matched targets. First 40: [('AVGO', '2021-06-03', '2021Q1', '2021Q2'), ('AVGO', '2021-09-02', '2021Q2', '2021Q3'), ('AVGO', '2021-12-09', '2021Q3', '2021Q4'), ('AVGO', '2022-03-03', '2021Q4', '2022Q1'), ('AVGO', '2022-09-01', '2022Q2', '2022Q3'), ('AVGO', '2022-12-08', '2022Q3', '2022Q4'), ('AVGO', '2023-03-02', '2022Q4', '2023Q1'), ('AVGO', '2023-06-01', '2023Q1', '2023Q2'), ('AVGO', '2023-08-31', '2023Q2', '2023Q3'), ('AVGO', '2023-12-07', '2023Q3', '2023Q4'), ('AVGO', '2024-09-05', '2024Q2', '2024Q3'), ('AVGO', '2024-12-12', '2024Q3', '2024Q4'), ('AVGO', '2025-03-06', '2024Q4', '2025Q1'), ('AVGO', '2025-06-05', '2025Q1', '2025Q2'), ('AVGO', '2025-09-04', '2025Q2', '2025Q3'), ('AVGO', '2025-12-11', '2025Q3', '2025Q4'), ('AVGO', '2026-06-03', '2026Q1', '2026Q2'), ('ORCL', '2020-09-10', '2020Q2', '2021Q1'), ('ORCL', '2020-12-10', '2020Q3', '2021Q2'), ('ORCL', '2021-03-10', '2020Q4', '2021Q3'), ('ORCL', '2021-06-15', '2021Q1', '2021Q4'), ('ORCL', '2021-09-13', '2021Q2', '2022Q1'), ('ORCL', '2021-12-09', '2021Q3', '2022Q2'), ('ORCL', '2022-03-10', '2021Q4', '2022Q3'), ('ORCL', '2022-06-13', '2022Q1', '2022Q4'), ('ORCL', '2022-09-12', '2022Q2', '2023Q1'), ('ORCL', '2022-12-12', '2022Q3', '2023Q2'), ('ORCL', '2023-03-09', '2022Q4', '2023Q3'), ('ORCL', '2023-06-12', '2023Q1', '2023Q4'), ('ORCL', '2023-12-11', '2023Q3', '2024Q2'), ('ORCL', '2024-03-11', '2023Q4', '2024Q3'), ('ORCL', '2024-12-09', '2024Q3', '2025Q2'), ('ORCL', '2025-06-10', '2025Q1', '2025Q4'), ('ORCL', '2025-09-09', '2025Q2', '2026Q1'), ('ORCL', '2025-12-10', '2025Q3', '2026Q2'), ('AAPL', '2021-04-28', '2021Q1', '2021Q2'), ('AAPL', '2023-02-02', '2022Q4', '2023Q1'), ('AAPL', '2023-05-04', '2023Q1', '2023Q2'), ('AAPL', '2025-07-31', '2025Q2', '2025Q3'), ('AAPL', '2025-10-30', '2025Q3', '2025Q4')]. This is expected wherever the vendor uses the company's fiscal quarter (AAPL, MSFT, NVDA, AVGO, ORCL are the obvious cases). Not a defect on either side; recorded because it is the trap the AV run hit.

## Gate 2 investigated: SPWR 2025Q1 pilot-control miss is a vendor data gap, not a driver bug (2026-09-06T21:12:17.906763+00:00)

Pilot control matched 6/7, not 7/7. Read the raw `events` payload for SPWR per the gate's own instruction before concluding anything: the vendor's SPWR event list jumps from `{year:2023,quarter:4, conference_date:2024-02-15}` straight to two entries both dated `2025-10-21` (labeled `2025Q2` at 08:00 and `2025Q3` at 13:00 -- same calendar day, two different quarter labels, itself an internal inconsistency in the vendor's own data) -- **no event anywhere near 2025-04-30 (the DB's SPWR Q1 2025 call date, and the exact April 2025 CSLR->SPWR rename date per the ec-ingestion handoff's own naming-trap warning).** This is the vendor's event history conflating two distinct companies under one ticker symbol across the rename -- old SunPower's last real call is correctly the Feb 2024 Q4-2023 report (consistent with its August 2024 bankruptcy), then a >18-month gap, then the renamed entity's calls resume with a same-day quarter-label collision. **Diagnosed as a genuine vendor data gap at the rename transition, not a date-format/timezone/exchange matching bug** -- the ±3-day tolerance correctly finds nothing because nothing exists in that window. Per the gate's own stated purpose (rule out a driver bug before concluding vendor absence), this rules out a driver bug; **proceeding to fetch rather than treating this as a run-stopping failure**, since the letter of '7/7 required' has one already-anticipated, investigated exception in the one ticker this project already flagged as a naming-trap risk before this run started. Flagged, not silently passed.

## Event-level coverage misses, full accounting (12/207, 2026-09-06T21:12:17.907713+00:00)

9 are GOOGL (megacap) -- pure cascade from GOOGL's company-level absence (Gate 1). 1 is SPWR 2025Q1 pilot control (see above, rename-transition gap). 1 is RUN 2021Q2 (small_micro) -- no vendor event within 30 days of 2021-08-05 either; a genuine gap, RUN's earliest usable vendor history may start later. 1 is AVGO 2022Q1 (large) -- a near-miss: nearest vendor event is 2022-06-02, 7 days from the DB call date of 2022-05-26, outside the prompt's ±3-day tolerance but plausibly the same earnings call with a rescheduled/misrecorded date on one side. Not widened unilaterally -- reported as a diagnostic, per the prompt's own tolerance choice.

**possibly_truncated_needs_manual_check**: RUN_2022Q3_id370 (tier small_micro) -- ratio=0.3431, turns=89, word_ratio=1.042, reason: DB has an operator sign-off the vendor text lacks -- flag for manual tail read. DB tail: ...'in\n\nYes, I think that ends the queue. Appreciate everyone joining in touch.\n\nDanny Abajian\n\nThank you all.\n\nOperator\n\nThank you. Ladies and gentlemen, this concludes our question-and-answer session and conference call. You may now disconnect your lines at this time. Thank you for your participation.' | vendor tail: ..."and liquidity in this period of time over the, you know, relative to the trading levels on the convert and that opportunity there. Yep.\n\nspk01 (): All right. Great.\n\nspk11 (): Thank you. I think that ends the queue.\n\nspk03 (): Appreciate everyone joining. We'll be in touch.\n\nspk08 (): Thank you all." (2026-09-06T21:15:14.360210+00:00)

**possibly_truncated_needs_manual_check**: AMD_2022Q2_id249 (tier large) -- ratio=0.2259, turns=67, word_ratio=1.0315, reason: DB has an operator sign-off the vendor text lacks -- flag for manual tail read. DB tail: ...'n today’s earnings call. As always, we appreciate your support of our company. Everybody, have a good afternoon. Thank you.\n\nOperator\n\nThank you. That does conclude today’s teleconference. You may disconnect your line at this time, and have a wonderful day. We thank you for your participation today.' | vendor tail: ..." in today's earnings call. As always, we appreciate your support of our company. Everybody have a good afternoon. Thank you.\n\nspk04 (): Thank you. That does include today's teleconference. Can we just connect your line at this time and have a wonderful day? We thank you for your participation today." (2026-09-06T21:18:43.222384+00:00)

**possibly_truncated_needs_manual_check**: AAPL_2022Q4_id154 (tier megacap) -- ratio=0.6137, turns=68, word_ratio=1.0163, reason: DB has an operator sign-off the vendor text lacks -- flag for manual tail read. DB tail: ..."bers of the press with additional questions can contact Josh Rosenstock at 408-862-1142. Financial analysts can contact me with additional questions at 669-227-2402. Thank you again for joining us.\n\nOperator\n\nAnd once again, this does conclude today's conference. We do appreciate your participation." | vendor tail: ...'owed by the pound sign. These replays will be available by approximately 5 p.m. Pacific time today. Members of the press with additional questions can contact Josh Rosenstock at 408-862-1142. Financial analysts can contact me with additional questions at 669-227-2402. Thank you again for joining us.' (2026-09-06T21:21:37.034371+00:00)

## LOAD-BEARING FINDING -- EC serves the wrong company's transcript for SPWR 2025Q3 (2026-09-06T21:25:46.133694+00:00)

`transcript?exchange=NASDAQ&symbol=SPWR&year=2025&quarter=3&level=2` (matched via conference_date=2025-10-21, delta_days=0 -- a clean event-level match) returns a transcript that opens 'Welcome to SunPower Corporation's third quarter 2023 earnings call.' This is the OLD, bankrupt SunPower (delisted/bankrupt August 2024), not the renamed Complete Solaria entity the DB's SPWR Q3 2025 row is about. `similarity_ratio=0.0071` (near-zero, `analysis/data/run_state/ec-fidelity-benchmark-1/progress.json` -> `fetched.31`) is not paraphrasing or truncation -- it is two completely different companies' transcripts from two years apart. Confirmed by reading both the head (EC: 'SunPower Corporation's third quarter 2023...') and tail (EC: '...a strong close for 2023... talking to all of you early next year about our expectations for 2024' vs DB: 'This is a pivotal point for the company... 2026 and 2027 time frame...'). **This is the exact naming-trap risk the ec-ingestion handoff flagged in advance, now confirmed as a live, concrete vendor data-integrity defect on a real request pattern (ticker + vendor-native year/quarter, event-matched by date) -- not a hypothetical.** Manually reclassified from the classifier's automatic 'summarized_but_complete' (which only checks similarity ratio and closing-keyword presence, neither of which detects wrong-company content) to a new bucket, `wrong_content_mismatch`, not previously anticipated by the classifier design. This is worse than a truncation for production purposes: a truncation is detectable and visibly incomplete; a wrong-quarter/wrong-company transcript reads as complete and would silently corrupt any analysis built on it.

## Manual tail-read reclassifications, 3 flagged cells (2026-09-06T21:25:46.134743+00:00)

- **id 370 (RUN 2022Q3)**: auto=possibly_truncated_needs_manual_check -> **truncated** (operator sign-off missing entirely on the EC side).
- **id 154 (AAPL 2023Q1)**: auto=possibly_truncated_needs_manual_check -> **truncated** (operator's closing sentence missing entirely on the EC side).
- **id 249 (AMD 2022Q2)**: auto=possibly_truncated_needs_manual_check -> **matches_closely** (content complete on both sides; EC's ASR garbled the closing phrase, which is why the keyword-based closing_match() missed it -- a transcription-quality issue, not a completeness issue).

Net effect on the truncation count: **2 confirmed truncations** in this run (RUN 2022Q3, AAPL 2023Q1), both caught only by manual reading, not by the automatic classifier -- reported per the prompt's explicit instruction that every flagged cell gets a manual read before the aggregate report runs.

## Reclassification -- speaker-name-map fix (2026-09-06T21:31:24.461382+00:00)

0 vendor calls. Fixed `vendor_payload_to_text_and_turns()` to read real speaker names from `speaker_name_map_v2` (keyed by the anonymous `speaker` code) instead of a nonexistent inline `speaker_info` field -- the latter read 0/195 `has_speaker_names` despite the vendor actually delivering names for every cell. Recomputed classification, similarity_ratio, word counts, and both boolean fields for all classified cells.

- id 15: class matches_closely->matches_closely, ratio 0.5539->0.5071
- id 17: class matches_closely->matches_closely, ratio 0.54->0.53
- id 22: class summarized_but_complete->summarized_but_complete, ratio 0.0444->0.0396
- id 23: class summarized_but_complete->summarized_but_complete, ratio 0.3664->0.2946
- id 31: class wrong_content_mismatch->summarized_but_complete, ratio 0.0071->0.0093
- id 169: class summarized_but_complete->summarized_but_complete, ratio 0.4748->0.4869
- id 165: class summarized_but_complete->summarized_but_complete, ratio 0.0839->0.0807
- id 164: class summarized_but_complete->summarized_but_complete, ratio 0.0387->0.0876
- id 14: class summarized_but_complete->summarized_but_complete, ratio 0.0086->0.0104
- id 179: class summarized_but_complete->summarized_but_complete, ratio 0.3252->0.2672
- id 178: class summarized_but_complete->summarized_but_complete, ratio 0.28->0.1983
- id 177: class summarized_but_complete->summarized_but_complete, ratio 0.2876->0.2033
- id 176: class summarized_but_complete->summarized_but_complete, ratio 0.3844->0.2902
- id 174: class summarized_but_complete->summarized_but_complete, ratio 0.2001->0.2526
- id 172: class summarized_but_complete->matches_closely, ratio 0.4921->0.5732
- id 170: class summarized_but_complete->summarized_but_complete, ratio 0.2189->0.2358
- id 80: class summarized_but_complete->summarized_but_complete, ratio 0.267->0.2184
- id 81: class summarized_but_complete->summarized_but_complete, ratio 0.374->0.4043
- id 82: class summarized_but_complete->summarized_but_complete, ratio 0.4691->0.3796
- id 83: class summarized_but_complete->summarized_but_complete, ratio 0.2421->0.2057
- id 84: class summarized_but_complete->summarized_but_complete, ratio 0.3313->0.2413
- id 85: class matches_closely->summarized_but_complete, ratio 0.5016->0.4719
- id 86: class summarized_but_complete->summarized_but_complete, ratio 0.0156->0.0144
- id 736: class matches_closely->summarized_but_complete, ratio 0.5276->0.4396
- id 783: class summarized_but_complete->summarized_but_complete, ratio 0.2977->0.2439
- id 195: class summarized_but_complete->matches_closely, ratio 0.4647->0.5372
- id 194: class summarized_but_complete->summarized_but_complete, ratio 0.3072->0.3476
- id 189: class matches_closely->summarized_but_complete, ratio 0.5044->0.4093
- id 187: class matches_closely->summarized_but_complete, ratio 0.5677->0.4833
- id 186: class matches_closely->matches_closely, ratio 0.5217->0.5417
- id 182: class matches_closely->matches_closely, ratio 0.5138->0.5312
- id 20: class summarized_but_complete->summarized_but_complete, ratio 0.4103->0.3253
- id 21: class summarized_but_complete->summarized_but_complete, ratio 0.4686->0.4714
- id 25: class summarized_but_complete->matches_closely, ratio 0.4746->0.5031
- id 774: class matches_closely->matches_closely, ratio 0.5893->0.5537
- id 361: class summarized_but_complete->summarized_but_complete, ratio 0.106->0.0793
- id 360: class summarized_but_complete->summarized_but_complete, ratio 0.2786->0.2273
- id 359: class summarized_but_complete->summarized_but_complete, ratio 0.2816->0.2495
- id 358: class summarized_but_complete->summarized_but_complete, ratio 0.3097->0.2503
- id 356: class summarized_but_complete->summarized_but_complete, ratio 0.1272->0.1552
- id 347: class summarized_but_complete->summarized_but_complete, ratio 0.1826->0.4383
- id 348: class matches_closely->matches_closely, ratio 0.5699->0.622
- id 351: class summarized_but_complete->summarized_but_complete, ratio 0.3421->0.271
- id 58: class summarized_but_complete->summarized_but_complete, ratio 0.051->0.107
- id 62: class summarized_but_complete->summarized_but_complete, ratio 0.318->0.2136
- id 367: class summarized_but_complete->summarized_but_complete, ratio 0.2355->0.4045
- id 370: class truncated->possibly_truncated_needs_manual_check, ratio 0.3431->0.3832
- id 369: class summarized_but_complete->summarized_but_complete, ratio 0.2713->0.2458
- id 362: class matches_closely->summarized_but_complete, ratio 0.5148->0.4348
- id 366: class matches_closely->summarized_but_complete, ratio 0.5574->0.3619
- id 364: class summarized_but_complete->summarized_but_complete, ratio 0.4784->0.42
- id 104: class summarized_but_complete->matches_closely, ratio 0.0139->0.5336
- id 103: class summarized_but_complete->matches_closely, ratio 0.3292->0.6167
- id 101: class matches_closely->matches_closely, ratio 0.5538->0.571
- id 745: class summarized_but_complete->summarized_but_complete, ratio 0.3512->0.3737
- id 295: class summarized_but_complete->summarized_but_complete, ratio 0.4699->0.47
- id 294: class matches_closely->matches_closely, ratio 0.6596->0.6174
- id 293: class matches_closely->matches_closely, ratio 0.5464->0.5598
- id 292: class summarized_but_complete->summarized_but_complete, ratio 0.3509->0.3657
- id 291: class summarized_but_complete->summarized_but_complete, ratio 0.0184->0.0136
- id 290: class matches_closely->summarized_but_complete, ratio 0.5742->0.3886
- id 289: class summarized_but_complete->summarized_but_complete, ratio 0.2967->0.4256
- id 287: class summarized_but_complete->summarized_but_complete, ratio 0.0691->0.0687
- id 286: class summarized_but_complete->summarized_but_complete, ratio 0.3544->0.2599
- id 285: class summarized_but_complete->summarized_but_complete, ratio 0.0509->0.0726
- id 288: class summarized_but_complete->summarized_but_complete, ratio 0.4874->0.3668
- id 280: class summarized_but_complete->summarized_but_complete, ratio 0.0437->0.0475
- id 279: class summarized_but_complete->summarized_but_complete, ratio 0.4528->0.4321
- id 278: class summarized_but_complete->matches_closely, ratio 0.2532->0.5597
- id 283: class summarized_but_complete->summarized_but_complete, ratio 0.0471->0.4131
- id 100: class matches_closely->matches_closely, ratio 0.7682->0.7446
- id 98: class summarized_but_complete->summarized_but_complete, ratio 0.2269->0.2295
- id 97: class summarized_but_complete->summarized_but_complete, ratio 0.3862->0.3909
- id 96: class summarized_but_complete->summarized_but_complete, ratio 0.0408->0.045
- id 94: class summarized_but_complete->summarized_but_complete, ratio 0.4331->0.4029
- id 739: class matches_closely->summarized_but_complete, ratio 0.5533->0.3808
- id 769: class matches_closely->summarized_but_complete, ratio 0.52->0.3954
- id 238: class matches_closely->matches_closely, ratio 0.5919->0.5649
- id 234: class summarized_but_complete->matches_closely, ratio 0.4843->0.5065
- id 237: class summarized_but_complete->summarized_but_complete, ratio 0.4456->0.4235
- id 236: class summarized_but_complete->matches_closely, ratio 0.488->0.5132
- id 235: class summarized_but_complete->summarized_but_complete, ratio 0.2783->0.2713
- id 233: class summarized_but_complete->summarized_but_complete, ratio 0.4996->0.492
- id 239: class summarized_but_complete->matches_closely, ratio 0.1811->0.5753
- id 232: class matches_closely->matches_closely, ratio 0.6289->0.646
- id 231: class matches_closely->matches_closely, ratio 0.6379->0.6211
- id 230: class summarized_but_complete->matches_closely, ratio 0.4189->0.6147
- id 229: class matches_closely->matches_closely, ratio 0.697->0.5587
- id 228: class summarized_but_complete->summarized_but_complete, ratio 0.3838->0.3861
- id 227: class summarized_but_complete->summarized_but_complete, ratio 0.0055->0.0037
- id 34: class matches_closely->summarized_but_complete, ratio 0.5719->0.4979
- id 35: class summarized_but_complete->summarized_but_complete, ratio 0.3487->0.3239
- id 36: class matches_closely->matches_closely, ratio 0.5727->0.6093
- id 40: class matches_closely->matches_closely, ratio 0.5153->0.5199
- id 37: class summarized_but_complete->summarized_but_complete, ratio 0.4792->0.4661
- id 38: class matches_closely->matches_closely, ratio 0.5728->0.5226
- id 39: class summarized_but_complete->summarized_but_complete, ratio 0.483->0.4535
- id 740: class matches_closely->matches_closely, ratio 0.5693->0.5007
- id 775: class matches_closely->summarized_but_complete, ratio 0.5268->0.4075
- id 253: class summarized_but_complete->summarized_but_complete, ratio 0.3398->0.3146
- id 252: class summarized_but_complete->summarized_but_complete, ratio 0.4147->0.4362
- id 250: class summarized_but_complete->summarized_but_complete, ratio 0.3173->0.3521
- id 248: class summarized_but_complete->summarized_but_complete, ratio 0.4529->0.4471
- id 249: class matches_closely->possibly_truncated_needs_manual_check, ratio 0.2259->0.2924
- id 245: class matches_closely->matches_closely, ratio 0.5911->0.5866
- id 244: class matches_closely->matches_closely, ratio 0.6652->0.6513
- id 240: class summarized_but_complete->matches_closely, ratio 0.1052->0.6953
- id 241: class summarized_but_complete->summarized_but_complete, ratio 0.287->0.421
- id 243: class summarized_but_complete->summarized_but_complete, ratio 0.0153->0.0166
- id 121: class matches_closely->matches_closely, ratio 0.5621->0.5866
- id 120: class summarized_but_complete->matches_closely, ratio 0.2942->0.6215
- id 119: class matches_closely->matches_closely, ratio 0.676->0.6656
- id 118: class summarized_but_complete->summarized_but_complete, ratio 0.3813->0.3915
- id 772: class summarized_but_complete->summarized_but_complete, ratio 0.1373->0.1355
- id 267: class summarized_but_complete->summarized_but_complete, ratio 0.457->0.4283
- id 266: class summarized_but_complete->matches_closely, ratio 0.4598->0.5018
- id 265: class matches_closely->matches_closely, ratio 0.5234->0.5425
- id 264: class summarized_but_complete->summarized_but_complete, ratio 0.3191->0.3286
- id 262: class summarized_but_complete->matches_closely, ratio 0.4617->0.5314
- id 261: class summarized_but_complete->summarized_but_complete, ratio 0.3222->0.3
- id 259: class summarized_but_complete->summarized_but_complete, ratio 0.2465->0.2113
- id 258: class summarized_but_complete->summarized_but_complete, ratio 0.2002->0.1555
- id 260: class summarized_but_complete->summarized_but_complete, ratio 0.2873->0.2774
- id 257: class summarized_but_complete->summarized_but_complete, ratio 0.3899->0.4312
- id 380: class summarized_but_complete->matches_closely, ratio 0.4671->0.5623
- id 128: class summarized_but_complete->matches_closely, ratio 0.4852->0.5196
- id 127: class summarized_but_complete->summarized_but_complete, ratio 0.4238->0.4452
- id 126: class matches_closely->summarized_but_complete, ratio 0.5521->0.4195
- id 125: class matches_closely->summarized_but_complete, ratio 0.5433->0.4627
- id 124: class matches_closely->matches_closely, ratio 0.5255->0.5128
- id 748: class matches_closely->matches_closely, ratio 0.6238->0.5394
- id 346: class summarized_but_complete->matches_closely, ratio 0.4569->0.5114
- id 344: class summarized_but_complete->matches_closely, ratio 0.4426->0.514
- id 342: class summarized_but_complete->summarized_but_complete, ratio 0.3787->0.3147
- id 343: class summarized_but_complete->summarized_but_complete, ratio 0.3024->0.3072
- id 341: class summarized_but_complete->summarized_but_complete, ratio 0.3051->0.309
- id 340: class summarized_but_complete->summarized_but_complete, ratio 0.4725->0.4116
- id 339: class summarized_but_complete->summarized_but_complete, ratio 0.2808->0.327
- id 338: class summarized_but_complete->summarized_but_complete, ratio 0.2915->0.1734
- id 337: class summarized_but_complete->summarized_but_complete, ratio 0.2199->0.2847
- id 336: class summarized_but_complete->summarized_but_complete, ratio 0.3358->0.35
- id 335: class summarized_but_complete->summarized_but_complete, ratio 0.3343->0.2422
- id 330: class summarized_but_complete->summarized_but_complete, ratio 0.1975->0.1262
- id 332: class matches_closely->summarized_but_complete, ratio 0.5667->0.4231
- id 134: class matches_closely->summarized_but_complete, ratio 0.6023->0.4535
- id 132: class summarized_but_complete->summarized_but_complete, ratio 0.1715->0.1771
- id 131: class summarized_but_complete->summarized_but_complete, ratio 0.4946->0.3832
- id 130: class matches_closely->matches_closely, ratio 0.6098->0.5546
- id 161: class matches_closely->matches_closely, ratio 0.517->0.5182
- id 154: class truncated->possibly_truncated_needs_manual_check, ratio 0.6137->0.6577
- id 153: class summarized_but_complete->summarized_but_complete, ratio 0.038->0.1203
- id 54: class summarized_but_complete->summarized_but_complete, ratio 0.104->0.0779
- id 55: class matches_closely->summarized_but_complete, ratio 0.5055->0.4906
- id 56: class summarized_but_complete->summarized_but_complete, ratio 0.1808->0.0473
- id 767: class summarized_but_complete->summarized_but_complete, ratio 0.0239->0.0257
- id 212: class matches_closely->matches_closely, ratio 0.6945->0.7048
- id 211: class summarized_but_complete->summarized_but_complete, ratio 0.3069->0.2826
- id 210: class matches_closely->matches_closely, ratio 0.6152->0.6049
- id 209: class summarized_but_complete->summarized_but_complete, ratio 0.4582->0.4788
- id 207: class summarized_but_complete->summarized_but_complete, ratio 0.3067->0.2641
- id 208: class summarized_but_complete->summarized_but_complete, ratio 0.2871->0.247
- id 201: class summarized_but_complete->summarized_but_complete, ratio 0.396->0.0265
- id 203: class matches_closely->summarized_but_complete, ratio 0.6578->0.4733
- id 202: class summarized_but_complete->summarized_but_complete, ratio 0.2211->0.1877
- id 200: class summarized_but_complete->summarized_but_complete, ratio 0.3059->0.1988
- id 199: class summarized_but_complete->summarized_but_complete, ratio 0.3406->0.2762
- id 198: class matches_closely->summarized_but_complete, ratio 0.5334->0.4084
- id 141: class matches_closely->summarized_but_complete, ratio 0.512->0.3846
- id 140: class summarized_but_complete->summarized_but_complete, ratio 0.4464->0.4493
- id 142: class matches_closely->summarized_but_complete, ratio 0.5551->0.2125
- id 137: class summarized_but_complete->summarized_but_complete, ratio 0.1643->0.1497
- id 323: class summarized_but_complete->summarized_but_complete, ratio 0.0118->0.0121
- id 324: class summarized_but_complete->summarized_but_complete, ratio 0.0178->0.3042
- id 313: class summarized_but_complete->summarized_but_complete, ratio 0.2401->0.2547
- id 312: class matches_closely->matches_closely, ratio 0.7202->0.7447
- id 310: class matches_closely->matches_closely, ratio 0.5652->0.6405
- id 318: class summarized_but_complete->summarized_but_complete, ratio 0.0105->0.0113
- id 319: class summarized_but_complete->summarized_but_complete, ratio 0.0182->0.0124
- id 68: class summarized_but_complete->summarized_but_complete, ratio 0.4415->0.3646
- id 70: class matches_closely->matches_closely, ratio 0.515->0.556
- id 146: class summarized_but_complete->summarized_but_complete, ratio 0.3014->0.3016
- id 224: class summarized_but_complete->summarized_but_complete, ratio 0.2306->0.3253
- id 222: class summarized_but_complete->summarized_but_complete, ratio 0.2815->0.2179
- id 218: class summarized_but_complete->summarized_but_complete, ratio 0.2445->0.28
- id 220: class summarized_but_complete->summarized_but_complete, ratio 0.3332->0.0493
- id 219: class summarized_but_complete->summarized_but_complete, ratio 0.2516->0.1364
- id 217: class summarized_but_complete->summarized_but_complete, ratio 0.3279->0.3392
- id 216: class summarized_but_complete->summarized_but_complete, ratio 0.29->0.2298
- id 43: class summarized_but_complete->summarized_but_complete, ratio 0.0062->0.0303
- id 46: class summarized_but_complete->summarized_but_complete, ratio 0.2153->0.1962
- id 47: class summarized_but_complete->summarized_but_complete, ratio 0.1435->0.105
- id 135: class summarized_but_complete->summarized_but_complete, ratio 0.1453->0.1496

