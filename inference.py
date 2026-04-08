"""
Baseline inference script for TLA+ Specification Verification Environment.

Runs an LLM agent against all 3 tasks and produces structured logs.
"""

import asyncio
import os
import sys
from typing import Dict, List, Optional

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tla_env import TlaEnv, TlaSpecAction

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-32B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_URL = os.getenv("ENV_URL", "https://sachinkumarsingh-tla-env.hf.space")
BENCHMARK = "tla_spec_env"

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

TASKS = ["fix_syntax", "write_invariant", "write_spec"]
MAX_STEPS_PER_TASK = {"fix_syntax": 5, "write_invariant": 5, "write_spec": 8}
SUCCESS_THRESHOLD = 0.8


def task_score_open_unit(raw: float) -> float:
    """Map grader score from [0, 1] to (0, 1) for validators that reject 0.0 and 1.0."""
    x = max(0.0, min(1.0, float(raw)))
    return 0.01 + 0.98 * x


SYSTEM_PROMPT = """You are an expert TLA+ specification writer.

When given a task, you write or fix TLA+ specifications.

IMPORTANT RULES:
- Output ONLY the complete TLA+ specification, nothing else.
- Do NOT include markdown code fences or explanations.
- Every TLA+ spec starts with: ---- MODULE <name> ----
- Every TLA+ spec ends with: ====
- Use == for definitions (not =)
- Use /\\ for conjunction, \\/ for disjunction
- UNCHANGED <<var1, var2>> for frame conditions
- [var EXCEPT ![key] = val] for function updates

When fixing errors, carefully compare with TLA+ syntax rules.
When writing invariants, use universal quantifiers: \\A i, j \\in Set : ...
When writing full specs, include all VARIABLES, Init, Next, and invariants."""


def _sanitize_action(action: str) -> str:
    """Collapse action text to a single line for log output."""
    return action.replace("\n", "\\n").replace("\r", "")


def log_start(task: str, env: str, model: str):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]):
    done_str = "true" if done else "false"
    error_str = error if error else "null"
    action_str = _sanitize_action(action)
    print(
        f"[STEP] step={step} action={action_str} reward={reward:.2f} "
        f"done={done_str} error={error_str}",
        flush=True,
    )


def log_end(success: bool, steps: int, rewards: List[float]):
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={success_str} steps={steps} rewards={rewards_str}",
        flush=True,
    )


def build_prompt(task_description: str, current_spec: str, feedback: str, step: int) -> str:
    parts = [f"TASK:\n{task_description}"]
    if current_spec:
        parts.append(f"CURRENT SPECIFICATION:\n{current_spec}")
    if feedback and step > 1:
        parts.append(f"FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback}")
    if step > 1:
        parts.append(
            f"This is attempt {step}. Carefully fix the issues from the feedback above."
        )
    return "\n\n".join(parts)


def get_model_response(client: OpenAI, prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text
    except Exception as e:
        print(f"Model request failed: {e}", file=sys.stderr, flush=True)
        return ""


async def run_task(client: OpenAI, env_url: str, task_id: str) -> Dict:
    max_steps = MAX_STEPS_PER_TASK.get(task_id, 5)

    rewards: List[float] = []
    steps_taken = 0
    raw_score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        async with TlaEnv(base_url=env_url) as env:
            result = await env.reset(task_id=task_id)
            obs = result.observation
            task_desc = obs.task_description
            current_spec = obs.current_spec
            feedback = obs.feedback

            for step in range(1, max_steps + 1):
                if result.done:
                    break

                prompt = build_prompt(task_desc, current_spec, feedback, step)
                spec_text = get_model_response(client, prompt)

                if not spec_text:
                    spec_text = current_spec if current_spec else "---- MODULE empty ----\n===="

                result = await env.step(TlaSpecAction(spec_text=spec_text))
                obs = result.observation

                reward = result.reward or 0.0
                done = result.done
                rewards.append(reward)
                steps_taken = step

                feedback = obs.feedback
                raw_score = obs.score

                log_step(step=step, action=spec_text, reward=reward, done=done, error=None)

                if done:
                    break

            success = raw_score >= SUCCESS_THRESHOLD

    except Exception as e:
        print(f"Task {task_id} error: {e}", file=sys.stderr, flush=True)
        log_step(step=steps_taken + 1, action="", reward=0.0, done=True, error=str(e))

    log_end(success=success, steps=steps_taken, rewards=rewards)
    return {
        "task_id": task_id,
        "score": task_score_open_unit(raw_score),
        "steps": steps_taken,
        "success": success,
    }


async def main():
    client = OpenAI(base_url=API_BASE_URL, api_key=HF_TOKEN)
    results = []

    for task_id in TASKS:
        result = await run_task(client, ENV_URL, task_id)
        results.append(result)

    print(
        f"\nSummary: "
        + " | ".join(
            f"{r['task_id']}={r['score']:.2f}"
            for r in results
        ),
        file=sys.stderr,
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
