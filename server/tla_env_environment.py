"""
TLA+ Specification Verification Environment.

An RL environment where agents write, fix, and complete TLA+ formal
specifications. Verified using SANY (syntax) and TLC (model checking).
"""

import os
import sys
from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment

_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    from models import TlaSpecAction, TlaSpecObservation, TlaSpecState
except ImportError:
    from tla_env.models import TlaSpecAction, TlaSpecObservation, TlaSpecState

try:
    from server.tasks import TASKS
except ImportError:
    from tla_env.server.tasks import TASKS


class TlaEnvironment(Environment):
    """
    TLA+ specification verification environment.

    The agent receives a task (fix syntax errors, write an invariant, or
    write a complete spec) and submits TLA+ specifications. The environment
    grades each submission using SANY and TLC, returning structured feedback
    and partial-credit rewards.

    Tasks:
        - fix_syntax (easy): Fix syntax errors in Peterson's Mutex
        - write_invariant (medium): Write mutual exclusion invariant for Token Ring
        - write_spec (hard): Write a complete Two-Phase Commit specification
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = TlaSpecState(episode_id=str(uuid4()), step_count=0)
        self._task = None
        self._best_score = 0.0
        self._last_spec = ""
        self._last_feedback = ""

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> TlaSpecObservation:
        task_id = kwargs.get("task_id", "fix_syntax")

        if task_id not in TASKS:
            return TlaSpecObservation(
                done=True,
                reward=0.0,
                task_id="",
                task_description=(
                    f"Unknown task '{task_id}'. "
                    f"Available: {list(TASKS.keys())}"
                ),
                current_spec="",
                feedback=f"Valid task IDs: {', '.join(TASKS.keys())}",
                score=0.0,
                attempts_remaining=0,
                available_tasks=list(TASKS.keys()),
            )

        self._task = TASKS[task_id]
        self._best_score = 0.0
        self._last_spec = ""
        self._last_feedback = ""

        self._state = TlaSpecState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=task_id,
            current_score=0.0,
            max_steps=self._task.max_steps,
        )

        return TlaSpecObservation(
            done=False,
            reward=0.0,
            task_id=task_id,
            task_description=self._task.description,
            current_spec=self._task.starting_spec,
            feedback=(
                f"Task: {self._task.name} ({self._task.difficulty}). "
                f"You have {self._task.max_steps} attempts. "
                "Submit your TLA+ specification."
            ),
            score=0.0,
            attempts_remaining=self._task.max_steps,
            available_tasks=list(TASKS.keys()),
        )

    def step(
        self,
        action: TlaSpecAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> TlaSpecObservation:
        if self._task is None:
            return TlaSpecObservation(
                done=True,
                reward=0.0,
                task_id="",
                task_description="No task active. Call reset(task_id=...) first.",
                current_spec="",
                feedback="Call reset() before step().",
                score=0.0,
                attempts_remaining=0,
            )

        self._state.step_count += 1
        remaining = self._task.max_steps - self._state.step_count

        spec_text = action.spec_text.strip()

        if spec_text == self._last_spec and self._last_spec:
            done = remaining <= 0
            return TlaSpecObservation(
                done=done,
                reward=-0.05,
                task_id=self._task.task_id,
                task_description=self._task.description,
                current_spec=self._task.starting_spec,
                feedback=(
                    "Identical submission (penalty -0.05). "
                    "Modify your specification.\n\n"
                    f"Previous feedback:\n{self._last_feedback}"
                ),
                score=self._best_score,
                attempts_remaining=max(0, remaining),
            )

        self._last_spec = spec_text

        step_score, feedback = self._task.grader(spec_text, self._task)

        reward = 0.0
        if step_score > self._best_score:
            reward = step_score - self._best_score
            self._best_score = step_score

        self._state.current_score = self._best_score
        self._last_feedback = feedback

        done = self._best_score >= 1.0 or remaining <= 0
        if done and self._best_score >= 1.0:
            feedback += "\n\nPerfect score achieved!"

        return TlaSpecObservation(
            done=done,
            reward=reward,
            task_id=self._task.task_id,
            task_description=self._task.description,
            current_spec=self._task.starting_spec,
            feedback=feedback,
            score=self._best_score,
            attempts_remaining=max(0, remaining),
        )

    @property
    def state(self) -> TlaSpecState:
        return self._state
