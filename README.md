# 🧬 adversagen

<div align="center">

**Adaptive red-team research for testing the resilience of AI-security scanners.**

[![CI](https://github.com/Pyhroff/adversagen/actions/workflows/ci.yml/badge.svg)](https://github.com/Pyhroff/adversagen/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Overview

Most scanners iterate on fixed payload lists.

`adversagen` turns scanner weaknesses into an experimental search problem: it evolves payloads and compares mutation strategies against a defined defense interface.

It is the **adversarial research layer of the Pyhroff AI-security portfolio** and intentionally remains a specialist experiment runner rather than an `aisec scan` module.

## Research model

Payloads combine goal phrasing with controlled obfuscation choices such as zero-width characters, homoglyph substitution, synonym paraphrase, and indirection.

Two mutation strategies are compared:

- **Reflection** — moves children toward the current high-fitness region.
- **Random mutation** — preserves more exploration diversity.

The project records measured evasion behavior rather than treating a successful payload as proof of scanner failure.

## Real-scanner mode

```bash
python3 experiment.py --real-scanners \
  --surfaces memory_injection,rag_injection,tool_poisoning \
  --seeds 2 --generations 2 --population 4 --samples 2
```

The real-scanner mode is deliberately small because it invokes scanner binaries as subprocesses.

## Relationship to aisec-suite

**aisec-suite** is the defensive product surface.

**adversagen** is the attack-side evaluation loop used to discover gaps and regression cases.

That separation keeps the umbrella focused on artifact scanning while preserving the research workflow.

## Safety boundary

Use only against your own fixtures, local test systems, or explicitly authorized defenses.

## Development

```bash
python3 -m pytest tests/ -q
```

## License

MIT
