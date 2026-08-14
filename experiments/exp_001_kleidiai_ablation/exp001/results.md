| build | threads | pp tok/s (mean, sd, n) | tg tok/s (mean, sd, n) |
|---|---|---|---|
| generic | 8 | 311.1, 0.18, 5 | 93.7, 0.42, 5 |
| generic | 16 | 494.1, 1.25, 5 | 140.9, 1.89, 5 |
| kleidiai | 8 | 315.8, 0.07, 5 | 87.6, 0.69, 5 |
| kleidiai | 16 | 500.1, 2.05, 5 | 120.1, 5.50, 5 |

| threads | KleidiAI pp speedup | KleidiAI tg speedup |
|---|---|---|
| t8 | 1.015x | 0.935x |
| t16 | 1.012x | 0.853x |

llama.cpp commit(s): 6fed9f6ff; model_size_bytes=1060276736; model_n_params=1777088000
