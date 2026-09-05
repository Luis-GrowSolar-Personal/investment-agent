## Step 0 -- draw (2026-09-05T18:19:53.190603+00:00)

Pool sizes: {'megacap': 114, 'large': 67, 'mid': 45, 'small_micro': 95}. Allocation: {'megacap': 52, 'large': 51, 'mid': 45, 'small_micro': 52}. Seed 20260905. 200 items drawn, saved to progress.json['drawn'].

## Step 0 -- draw (2026-09-05T18:20:41.561085+00:00)

Pool sizes: {'megacap': 114, 'large': 67, 'mid': 45, 'small_micro': 97}. Allocation: {'megacap': 52, 'large': 51, 'mid': 45, 'small_micro': 52}. Seed 20260905. 200 items drawn, saved to progress.json['drawn'].

## Step 0 -- draw (2026-09-05T18:21:07.574107+00:00)

Pool sizes: {'megacap': 114, 'large': 67, 'mid': 44, 'small_micro': 97}. Allocation: {'megacap': 53, 'large': 51, 'mid': 44, 'small_micro': 52}. Seed 20260905. 200 items drawn, saved to progress.json['drawn'].

## Step 0 method note -- quarter-label mapping and dedup (2026-09-05T18:21:21.915469+00:00)

Flagged premise (not stated in the prompt, discovered during Step 0): a flat 45-day-offset heuristic for mapping DB callDate -> AV `quarter` param collapses a company's Jan-Mar call (reports prior-year Q4) and its Apr-Jun call (reports current-year Q1) onto the same label when both occur in the same calendar year. Confirmed present in this corpus for FSLR, TTD, QS, ENVX, RUN. Replaced with a call-month bucket (Jan-Mar->priorYearQ4, Apr-Jun->Q1, Jul-Sep->Q2, Oct-Dec->Q3), validated to reproduce every known-correct label from benchmark_1 and Test 3 exactly (AMPX/EOSE/SPWR). Caught before any AV call was spent.

Separately found one genuine DB-side duplicate: FSLR ids 280 and 284 are identical rows (same callDate 2024-02-27, same title, identical rawText length 57254) for Q4 2023. Dropped id 284 from the pool (kept lower id) to avoid spending two AV calls to compare against what is really one DB transcript. mid-tier pool is therefore 44, not 45 as the prompt's 2026-09-05 table states; target allocation recomputed per the prompt's own fallback rule (cap at pool, spread remainder evenly) to megacap 53 / large 51 / mid 44 / small_micro 52.

**truncated**: NVDA_2022Q3 (tier megacap, transcript id 313) -- ratio=0.0225, turns=27, reason: AV's last turn hands off to a named speaker for closing remarks that never appear. DB tail: ...'through general purchase computing alone is no longer viable, both from a cost or power standpoint. Accelerated computing is the path forward. We look forward to updating you on our progress next quarter.\n\nOperator\n\nThis concludes today’s conference call. Thank you for attending. You may disconnect.' | AV tail: ..."er to Jensen for closing remarks. Well, I think we just heard the closing remarks. Thank you so much for joining us. We look forward to seeing everybody at the conferences that we have planned over the next few months, and I'm sure we'll talk before the end of next earnings. Thanks again, everybody." (2026-09-05T18:35:41.405840+00:00)

**possibly_truncated_needs_manual_check**: AAPL_2023Q1 (tier megacap, transcript id 153) -- ratio=0.0389, turns=54, reason: DB has an operator sign-off AV lacks -- flag for manual tail read. DB tail: ..."embers of the press with additional questions can contact Josh Rosenstock at 488-\u206062-\u20601142 and financial analysts can contact me with additional questions at 408-\u2060862-\u20605119. Thanks again for joining us.\n\nOperator\n\nOnce again, this does conclude today's conference. We do appreciate your participation" | AV tail: ..." press with additional questions can contact Josh Rosenstock at 408-862-1142. Financial analysts can contact me with additional questions at 669-227-2402. Thank you again for joining us.\n\nOperator (Operator): And once again, this does conclude today's conference. We do appreciate your participation." (2026-09-05T18:39:13.952851+00:00)

## Reclassification after fixing handoff/keyword heuristic (2026-09-05T18:45:21.628037+00:00)

Fixed two classifier bugs: (1) a handoff phrase (e.g. 'closing remarks') anywhere in the last turn was flagged truncated even when resolved in the same turn -- now only flagged when it sits within 80 trailing chars of the turn's end; (2) closing-keyword list missed 'does conclude' phrasing. Re-ran classify_sample over all already-fetched raw/ files, 0 new AV calls.

- **NVDA_2022Q3**: truncated -> summarized_but_complete
- **AAPL_2023Q1**: possibly_truncated_needs_manual_check -> summarized_but_complete

## Flagged premise mismatch -- prompt update vs recorded Day 1 state (2026-09-05T19:00:19.570861+00:00)

The prompt's 2026-09-05 'after day 1' update states Day 1 was '10 calls, all megacap, single key.' The actual recorded Day 1 batch in progress.json is **20 calls**, all megacap, single key (AV_API_KEY) -- matching this run's own wrap-up (`av_transcript_fidelity_benchmark_2_stratified-out.md`), not the prompt's restated figure. Per Step 4 (verify the premise before implementing): kept the actual recorded 20-call batch as-is (the prompt's own instruction is to leave Day 1 alone regardless), did not re-fetch or discard anything, and flagged the mismatch rather than silently adopting the prompt's wrong number.

**Coverage miss**: MSFT_2020Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:00:34.147121+00:00)

**Coverage miss**: TSLA_2025Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:00:34.227131+00:00)

**Coverage miss**: NVDA_2022Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:00:34.306961+00:00)

**Coverage miss**: NVDA_2023Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:00:34.400540+00:00)

**Coverage miss**: TSLA_2023Q2 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:38.140692+00:00)

**Coverage miss**: TSLA_2022Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:40.095297+00:00)

**Coverage miss**: MSFT_2022Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:41.300329+00:00)

**Coverage miss**: TSLA_2021Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:42.073395+00:00)

**Coverage miss**: GOOGL_2022Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:43.152395+00:00)

**Coverage miss**: TSLA_2025Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:44.142106+00:00)

**Coverage miss**: GOOGL_2023Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:44.740224+00:00)

**Coverage miss**: MSFT_2024Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:44.827879+00:00)

**Coverage miss**: MSFT_2022Q2 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:01:44.920489+00:00)

**Coverage miss**: TSLA_2024Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:48.124901+00:00)

**Coverage miss**: MSFT_2024Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:50.101945+00:00)

**Coverage miss**: GOOGL_2023Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:51.309884+00:00)

**Coverage miss**: GOOGL_2025Q3 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:52.078994+00:00)

**Coverage miss**: TSLA_2022Q2 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:53.160509+00:00)

**Coverage miss**: NVDA_2021Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:54.148067+00:00)

**Coverage miss**: MSFT_2025Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:54.758154+00:00)

**Coverage miss**: MSFT_2023Q2 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:54.854119+00:00)

**Coverage miss**: NVDA_2025Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:02:54.942470+00:00)

**Coverage miss**: MSFT_2023Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:03:58.127808+00:00)

**Coverage miss**: MSFT_2020Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:04:00.124277+00:00)

**Coverage miss**: MSFT_2021Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:04:01.316122+00:00)

**Coverage miss**: MSFT_2022Q1 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:04:02.155636+00:00)

**Coverage miss**: AAPL_2025Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:04:03.166270+00:00)

**Coverage miss**: NVDA_2020Q4 (tier megacap) -- AV returned no transcript entries. (2026-09-05T19:04:04.161232+00:00)

**Coverage miss**: ORCL_2023Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:04:04.757860+00:00)

**Coverage miss**: AMD_2024Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:04:05.361187+00:00)

**Coverage miss**: AVGO_2024Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:04:05.452137+00:00)

**Coverage miss**: ORCL_2022Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:08.135217+00:00)

**Coverage miss**: ORCL_2022Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:10.099117+00:00)

**Coverage miss**: AVGO_2025Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:11.320335+00:00)

**Coverage miss**: AVGO_2025Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:12.087492+00:00)

**Coverage miss**: AVGO_2026Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:13.159649+00:00)

**Coverage miss**: AMD_2023Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:14.167119+00:00)

**Coverage miss**: AVGO_2021Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:14.762867+00:00)

**Coverage miss**: ORCL_2023Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:15.364738+00:00)

**Coverage miss**: AVGO_2022Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:05:15.451844+00:00)

**Coverage miss**: AMD_2023Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:18.127703+00:00)

**Coverage miss**: ORCL_2021Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:20.132925+00:00)

**Coverage miss**: AVGO_2022Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:21.323393+00:00)

**Coverage miss**: ORCL_2020Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:22.086289+00:00)

**Coverage miss**: AVGO_2023Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:23.168725+00:00)

**Coverage miss**: AMD_2022Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:24.174168+00:00)

**Coverage miss**: ORCL_2021Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:24.798614+00:00)

**Coverage miss**: ORCL_2025Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:25.402941+00:00)

**Coverage miss**: AVGO_2023Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:06:25.493226+00:00)

**Coverage miss**: AVGO_2024Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:28.181015+00:00)

**Coverage miss**: AMD_2021Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:30.129460+00:00)

**Coverage miss**: AMD_2021Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:31.348894+00:00)

**Coverage miss**: ORCL_2020Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:32.097701+00:00)

**Coverage miss**: AMD_2024Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:33.176425+00:00)

**Coverage miss**: AMD_2021Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:34.175753+00:00)

**Coverage miss**: AVGO_2022Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:34.786419+00:00)

**Coverage miss**: AVGO_2021Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:35.410665+00:00)

**Coverage miss**: AVGO_2021Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:07:35.505739+00:00)

**Coverage miss**: ORCL_2022Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:38.156709+00:00)

**Coverage miss**: ORCL_2025Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:40.137277+00:00)

**Coverage miss**: AMD_2024Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:41.353921+00:00)

**Coverage miss**: ORCL_2024Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:42.108251+00:00)

**Coverage miss**: AMD_2024Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:43.177939+00:00)

**Coverage miss**: AMD_2026Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:44.212457+00:00)

**Coverage miss**: ORCL_2021Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:44.820405+00:00)

**Coverage miss**: ORCL_2021Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:45.427046+00:00)

**Coverage miss**: AMD_2025Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:08:45.525269+00:00)

**Coverage miss**: AVGO_2023Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:48.166127+00:00)

**Coverage miss**: AMD_2023Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:50.131919+00:00)

**Coverage miss**: AVGO_2022Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:51.348263+00:00)

**Coverage miss**: ORCL_2020Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:52.106296+00:00)

**Coverage miss**: ORCL_2023Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:53.185595+00:00)

**Coverage miss**: AVGO_2025Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:54.186219+00:00)

**Coverage miss**: AVGO_2021Q4 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:54.818782+00:00)

**Coverage miss**: ORCL_2025Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:55.431883+00:00)

**Coverage miss**: AMD_2022Q2 (tier large) -- AV returned no transcript entries. (2026-09-05T19:09:55.529088+00:00)

**Coverage miss**: AVGO_2024Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:10:58.186909+00:00)

**Coverage miss**: ORCL_2022Q3 (tier large) -- AV returned no transcript entries. (2026-09-05T19:11:00.171652+00:00)

**Coverage miss**: AMD_2025Q1 (tier large) -- AV returned no transcript entries. (2026-09-05T19:11:01.366343+00:00)

**Coverage miss**: FSLR_2023Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:02.112010+00:00)

**Coverage miss**: TTD_2024Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:03.192327+00:00)

**Coverage miss**: FSLR_2023Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:04.191737+00:00)

**Coverage miss**: FSLR_2021Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:04.823623+00:00)

**Coverage miss**: FSLR_2021Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:05.446467+00:00)

**Coverage miss**: FSLR_2025Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:11:05.533431+00:00)

**Coverage miss**: TTD_2026Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:08.688323+00:00)

**Coverage miss**: FSLR_2022Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:10.152039+00:00)

**Coverage miss**: FSLR_2021Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:11.355760+00:00)

**Coverage miss**: FSLR_2026Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:12.110297+00:00)

**Coverage miss**: FSLR_2025Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:13.190504+00:00)

**Coverage miss**: FSLR_2023Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:14.200466+00:00)

**Coverage miss**: FSLR_2024Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:14.822908+00:00)

**Coverage miss**: TTD_2024Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:15.445174+00:00)

**Coverage miss**: TTD_2022Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:12:15.538608+00:00)

**Coverage miss**: TTD_2023Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:18.710964+00:00)

**Coverage miss**: TTD_2026Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:20.160139+00:00)

**Coverage miss**: TTD_2021Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:21.364763+00:00)

**Coverage miss**: FSLR_2022Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:22.119438+00:00)

**Coverage miss**: TTD_2022Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:23.199487+00:00)

**Coverage miss**: TTD_2021Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:24.209965+00:00)

**Coverage miss**: FSLR_2022Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:24.827961+00:00)

**Coverage miss**: TTD_2022Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:25.450240+00:00)

**Coverage miss**: TTD_2025Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:13:25.543178+00:00)

**Coverage miss**: TTD_2023Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:28.708885+00:00)

**Coverage miss**: TTD_2025Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:30.154471+00:00)

**Coverage miss**: FSLR_2024Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:31.377103+00:00)

**Coverage miss**: FSLR_2025Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:32.137051+00:00)

**Coverage miss**: FSLR_2021Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:33.221855+00:00)

**Coverage miss**: FSLR_2024Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:34.210086+00:00)

**Coverage miss**: TTD_2023Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:34.835033+00:00)

**Coverage miss**: TTD_2022Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:35.459160+00:00)

**Coverage miss**: TTD_2023Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:14:35.550121+00:00)

**Coverage miss**: TTD_2024Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:38.775209+00:00)

**Coverage miss**: TTD_2025Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:40.170401+00:00)

**Coverage miss**: FSLR_2023Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:41.377564+00:00)

**Coverage miss**: TTD_2021Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:42.145871+00:00)

**Coverage miss**: FSLR_2024Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:43.227005+00:00)

**Coverage miss**: FSLR_2022Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:44.216667+00:00)

**Coverage miss**: FSLR_2025Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:44.839654+00:00)

**Coverage miss**: TTD_2025Q4 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:45.468015+00:00)

**Coverage miss**: TTD_2024Q3 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:15:45.558105+00:00)

**Coverage miss**: FSLR_2026Q2 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:16:48.789216+00:00)

**Coverage miss**: TTD_2021Q1 (tier mid) -- AV returned no transcript entries. (2026-09-05T19:16:50.165240+00:00)

**Coverage miss**: QS_2024Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:51.375057+00:00)

**Coverage miss**: ENVX_2022Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:52.149411+00:00)

**Coverage miss**: ENVX_2026Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:53.222864+00:00)

**Coverage miss**: QS_2024Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:54.232258+00:00)

**Coverage miss**: ENVX_2025Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:54.848517+00:00)

**Coverage miss**: AMPX_2023Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:55.519001+00:00)

**Coverage miss**: RUN_2024Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:16:55.611243+00:00)

**Coverage miss**: AMPX_2025Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:17:58.803626+00:00)

**Coverage miss**: RUN_2022Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:00.232911+00:00)

**Coverage miss**: QS_2021Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:01.382669+00:00)

**Coverage miss**: EOSE_2021Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:02.164703+00:00)

**Coverage miss**: RUN_2023Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:03.238011+00:00)

**Coverage miss**: QS_2023Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:04.234513+00:00)

**Coverage miss**: EOSE_2022Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:04.857532+00:00)

**Coverage miss**: AMPX_2022Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:05.466935+00:00)

**Coverage miss**: EOSE_2024Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:18:06.071785+00:00)

**Coverage miss**: RUN_2023Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:08.800786+00:00)

**Coverage miss**: RUN_2025Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:10.177547+00:00)

**Coverage miss**: ENVX_2023Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:11.401027+00:00)

**Coverage miss**: RUN_2025Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:12.165997+00:00)

**Coverage miss**: QS_2025Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:13.235880+00:00)

**Coverage miss**: ENVX_2026Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:14.228044+00:00)

**Coverage miss**: EOSE_2024Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:14.866714+00:00)

**Coverage miss**: ENVX_2021Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:15.481949+00:00)

**Coverage miss**: ENVX_2025Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:19:16.099878+00:00)

**Coverage miss**: QS_2022Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:18.804700+00:00)

**Coverage miss**: QS_2024Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:20.205793+00:00)

**Coverage miss**: EOSE_2023Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:21.397384+00:00)

**Coverage miss**: EOSE_2025Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:22.178178+00:00)

**Coverage miss**: AMPX_2023Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:23.238521+00:00)

**Coverage miss**: RUN_2026Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:24.240392+00:00)

**Coverage miss**: ENVX_2025Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:24.875189+00:00)

**Coverage miss**: EOSE_2026Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:25.482758+00:00)

**Coverage miss**: ENVX_2022Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:20:26.112719+00:00)

**Coverage miss**: RUN_2023Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:28.839302+00:00)

**Coverage miss**: ENVX_2025Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:30.202987+00:00)

**Coverage miss**: RUN_2021Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:31.411603+00:00)

**Coverage miss**: ENVX_2022Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:32.202048+00:00)

**Coverage miss**: QS_2021Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:33.255134+00:00)

**Coverage miss**: ENVX_2023Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:34.258002+00:00)

**Coverage miss**: QS_2021Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:34.890056+00:00)

**Coverage miss**: EOSE_2024Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:35.508877+00:00)

**Coverage miss**: ENVX_2024Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:21:36.122057+00:00)

**Coverage miss**: ENVX_2024Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:38.819268+00:00)

**Coverage miss**: RUN_2025Q4 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:40.210402+00:00)

**Coverage miss**: EOSE_2021Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:41.472642+00:00)

**Coverage miss**: AMPX_2024Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:42.189088+00:00)

**Coverage miss**: ENVX_2024Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:43.249414+00:00)

**Coverage miss**: EOSE_2023Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:44.268569+00:00)

**Coverage miss**: RUN_2022Q1 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:44.885915+00:00)

**Coverage miss**: QS_2021Q3 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:45.505386+00:00)

**Coverage miss**: ENVX_2024Q2 (tier small_micro) -- AV returned no transcript entries. (2026-09-05T19:22:46.121691+00:00)

## Bug found and fixed mid-run: is_rate_limited() false negative (2026-09-05T19:25:37.419264+00:00)

**Severity: high -- this corrupted Day 2's initial output before being caught.** `is_rate_limited()` checked `"information" in data` (lowercase), but AV's real field is `"Information"` (capital I) -- a case-sensitive dict KEY lookup, not a substring search, so it never matched. Every one of the 9 new keys (AV_API_KEY2-10) returned AV's real rate-limit message ("We have detected your API key as X and our standard API rate limit is 25 requests per day...") on or near its very first call today, and all 175 such responses were silently misfiled as `coverage_miss` (i.e. 'AV has no data for this ticker/quarter') rather than recognized as rate-limited.

**This would have directly corrupted the coverage-miss-rate-by-tier finding** -- large/mid/small_micro tiers showed 100% coverage miss, megacap showed 53% (28/53), which is not a real AV-coverage signal, it's every non-AV_API_KEY key being immediately rate-limited.

**Repair performed, 0 new AV calls spent:** fixed `is_rate_limited()` to match on the response's own values (case-insensitive substring), then replayed all 200 cells.jsonl entries through the corrected check. Confirmed all 175 coverage_miss records were rate-limit responses, 0 were genuine. Reverted all 175 back to unfetched in progress.json so they get retried against a real quota.

**Consequence for the multi-key premise:** AV_API_KEY2 through AV_API_KEY6 each returned exactly 1 successful real fetch before rate-limiting; AV_API_KEY7-10 returned 0. This is the exact failure mode the prompt's own update warned about -- 'if all ... keys turn out to share one account's quota, they are not additive.' Per the prompt's own defensive rule, all 9 keys beyond the original AV_API_KEY are now marked `disabled` in `key_usage` with reason 'suspected shared quota or already-exhausted account.' **Effective conclusion: despite being 10 distinct key strings on 10 different registered accounts, they do not behave as 10 independent 25/day budgets** -- consistent with either shared IP-level throttling on AV's side, or the accounts already having non-trivial usage today from something else. This run reverts to single-key (AV_API_KEY) operation, 20 calls/day, ~9 more invocations needed for the 175 remaining items -- the multi-key speedup did not materialize.

