---
title: TLA+ Specification Verification Environment
emoji: 🔬
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# TLA+ Specification Verification Environment

A real-world OpenEnv environment where AI agents learn to write, fix, and
complete [TLA+](https://en.wikipedia.org/wiki/TLA+) formal
specifications for distributed systems. Specifications are verified using
**SANY** (syntax analysis) and **TLC** (model checking).

## Motivation

TLA+ is used at Amazon, Microsoft, and Intel to formally verify distributed
systems and protocols. Writing correct TLA+ specifications requires substantial
expertise, creating a bottleneck in formal verification adoption. While large language models have shown promise in automating proofs for tactic-based theorem provers like Lean, applying these approaches directly to TLA+ faces significant challenges due to the hierarchical proof structure of the TLA+ proof system. This
environment provides a training ground for AI agents to learn specification
writing, bridging toward automated proof generation.

## Tasks

| # | Task ID | Difficulty | What the Agent Does | Max Steps |
|---|---------|------------|---------------------|-----------|
| 1 | `fix_syntax` | Easy | Fix 2 syntax errors in Peterson's Mutex | 5 |
| 2 | `write_invariant` | Medium | Write mutual exclusion invariant for Token Ring | 5 |
| 3 | `write_spec` | Hard | Write complete Two-Phase Commit specification | 8 |

### Task 1: Fix Syntax Errors (Easy)

A Peterson's Mutex specification with two syntax bugs:
- `Request(i) =` uses `=` instead of `==`
- `Enter(i)` has a missing closing bracket `]`

**Grading**: 0.4 for parse success, 0.2 for fixing both specific errors,
0.4 for TLC verification of MutualExclusion invariant.

### Task 2: Write Safety Invariant (Medium)

A Token Ring protocol with Init and Next fully defined. The agent must
replace the placeholder `MutualExclusion == TRUE` with a real invariant
stating at most one process is in the critical section.

**Grading**: 0.3 for parseable invariant, 0.1 for structural quality,
0.6 for TLC verification with N=3.

### Task 3: Write Two-Phase Commit Spec (Hard)

Given a natural language description of Two-Phase Commit, write the
complete TLA+ spec with all variables, actions, and the
ConsistencyInvariant (no RM committed while another aborted).

**Grading**: 0.15 parse, 0.15 structure, 0.1 invariant definition,
0.6 TLC verification with RM={r1,r2,r3}.

## Action Space

**TlaSpecAction**:
| Field | Type | Description |
|-------|------|-------------|
| `spec_text` | `str` | Complete TLA+ specification text |

## Observation Space

**TlaSpecObservation**:
| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `str` | Active task identifier |
| `task_description` | `str` | Full task instructions |
| `current_spec` | `str` | Starting spec (for fix/complete tasks) |
| `feedback` | `str` | SANY/TLC errors or verification results |
| `score` | `float` | Best score so far (0.0-1.0) |
| `attempts_remaining` | `int` | Steps left in episode |
| `done` | `bool` | Episode finished |
| `reward` | `float` | Reward from this step |

## Reward Design

- Rewards reflect incremental improvement: reward = max(0, new_score - best_score)
- Partial credit for parsing, structural correctness, and verification
- Penalty of -0.05 for submitting identical specs
- Score is the high-water mark across all steps

## Quick Start

```python
from tla_env import TlaEnv, TlaSpecAction

async with TlaEnv(base_url="https://sachinkumarsingh-tla-env.hf.space") as env:
    result = await env.reset(task_id="fix_syntax")
    print(result.observation.task_description)
    print(result.observation.current_spec)

    result = await env.step(TlaSpecAction(spec_text="---- MODULE mutex ----\n..."))
    print(result.observation.feedback)
    print(f"Score: {result.observation.score}")
```

## Setup

```bash
uv sync

# Install dependencies
uv pip install -r tla_env/requirements.txt

# Clone and install
uv pip install -e tla_env/


# Or with Docker
docker build -t tla-env -f Dockerfile .
docker run -p 8000:8000 tla-env
```

## Baseline Inference

```bash
export HF_TOKEN="your_huggingface_token"
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME="Qwen/Qwen2.5-Coder-32B-Instruct"
export ENV_URL=https://sachinkumarsingh-tla-env.hf.space

python3 inference.py
```

| Model | fix_syntax | write_invariant | write_spec | Mean |
|-------|------------|-----------------|------------|------|
| Qwen2.5-Coder-32B-Instruct | 0.98 | 0.98 | 0.06 | 0.67 |
| Qwen2.5-Coder-7B-Instruct | 0.98 | 0.16 | 0.06 | 0.40 |
| Llama-3.1-8B-Instruct | 0.60 | 0.16 | 0.16 | 0.31 |

## Deploy to Hugging Face Spaces

```bash
cd tla_env
openenv push --repo-id sachinkumarsingh/tla-env
```

## Technology

- **SANY**: TLA+ Syntactic Analyzer (syntax checking)
- **TLC**: TLA+ Model Checker (invariant verification)
- **OpenEnv**: RL environment framework (step/reset/state API)
- **FastAPI**: HTTP + WebSocket server
- **Docker**: Containerized deployment with JRE + tla2tools.jar

## Reference

1. [Towards Language Model Guided TLA+ Proof Automation](https://arxiv.org/abs/2512.09758)
2. [DeepSeek-Prover-V2](https://github.com/deepseek-ai/DeepSeek-Prover-V2)