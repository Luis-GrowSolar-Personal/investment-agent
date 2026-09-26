# findings (append-only)
- Step 2 (results.json): averaged B rank 0.121 (0.043-0.194); averaged P9 0.140 (0.055-0.223); paired avgP9 minus avgB +0.0196 (-0.0298 to +0.0692). Lower end -0.0298 >= -0.03 by 0.0002 -> pre-registered reading: worth a tune test, equal ranking (range includes zero), plus severity.
- Diagnostic only (seed_sensitivity.json): under other bootstrap seeds (1,2,3,4) the lower end is -0.0335, -0.0286, -0.0322, -0.0308: 3 of 4 alternates fall below -0.03. The reading holds at the fixed seed 11 by a margin smaller than bootstrap noise.
- Severity: avg P9 within bottom 191 0.222 (0.067-0.345) excludes zero; avg B 0.141 (-0.014-0.286) includes zero. Fifths avg P9 -9.06,-5.32,+0.04,-1.90,+0.19; avg B -7.88,-5.32,-1.81,-0.81,-0.65.
- Averaging helped little: B +0.006, P9 -0.001 over the mean of single-draw rankings.
