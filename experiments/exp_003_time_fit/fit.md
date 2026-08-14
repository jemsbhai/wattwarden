# EXP-003a fit: TOML decode time structure (Axion V2, EXP-002 data)

## Per thread level: time/token vs model bytes across quants

| threads | effective GB/s | intercept ms | R^2 | Q4_0 resid ms | Q4_K_M resid ms | Q8_0 resid ms |
|---|---|---|---|---|---|---|
| 1 | 87 | 50.53 | 0.610 | -4.14 | +4.41 | -0.27 |
| 2 | 222 | 29.65 | 0.585 | -1.70 | +1.81 | -0.11 |
| 4 | 469 | 16.90 | 0.414 | -1.14 | +1.21 | -0.07 |
| 8 | 720 | 9.98 | 0.451 | -0.69 | +0.73 | -0.05 |
| 16 | 624 | 17.65 | 0.870 | -0.28 | +0.30 | -0.02 |

## Per quant: time/token vs 1/threads (t in {1,2,4,8}; t16 excluded)

| quant | floor A ms (fit) | floor ms predicted from 150 GB/s | parallel B ms | R^2 |
|---|---|---|---|---|
| Q4_0 | 4.44 | 7.11 | 54.67 | 0.9990 |
| Q4_K_M | 4.55 | 7.45 | 63.39 | 0.9999 |
| Q8_0 | 3.95 | 12.63 | 68.16 | 1.0000 |

Interpretation is written in LOGBOOK.md (EXP-003a results), not here: this file is the mechanical fit output.
