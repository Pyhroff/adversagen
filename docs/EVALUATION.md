# adversagen Evaluation Methodology

adversagen evaluates whether defensive scanners remain robust when payloads are mutated rather than copied from a fixed list.

Compare reflection-guided mutation against a random-mutation control across the same seeds, population sizes, generations and sampling budget.

Report mean and dispersion, Welch and Mann-Whitney p-values, and an effect size such as Cohen's d. Record the exact scanner and fixture versions used.

Real-scanner experiments should use only authorized local or explicitly permitted targets. Keep attack fixtures bounded and harmless.

Interpretation boundary: an evasion rate is evidence about the tested scanner, payload generator, corpus and configuration. It is not a universal statement about model or scanner security.