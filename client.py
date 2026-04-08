"""TLA+ Specification Environment Client."""

from typing import Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

from .models import TlaSpecAction, TlaSpecObservation, TlaSpecState


class TlaEnv(EnvClient[TlaSpecAction, TlaSpecObservation, TlaSpecState]):
    """
    Client for the TLA+ Specification Verification Environment.

    Example:
        >>> async with TlaEnv(base_url="http://localhost:8000") as env:
        ...     result = await env.reset(task_id="fix_syntax")
        ...     print(result.observation.task_description)
        ...     result = await env.step(TlaSpecAction(spec_text="---- MODULE ..."))
        ...     print(result.observation.feedback)
    """

    def _step_payload(self, action: TlaSpecAction) -> Dict:
        return {"spec_text": action.spec_text}

    def _parse_result(self, payload: Dict) -> StepResult[TlaSpecObservation]:
        obs_data = payload.get("observation", {})
        observation = TlaSpecObservation(
            done=payload.get("done", False),
            reward=payload.get("reward"),
            task_id=obs_data.get("task_id", ""),
            task_description=obs_data.get("task_description", ""),
            current_spec=obs_data.get("current_spec", ""),
            feedback=obs_data.get("feedback", ""),
            score=obs_data.get("score", 0.0),
            attempts_remaining=obs_data.get("attempts_remaining", 0),
            available_tasks=obs_data.get("available_tasks"),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> TlaSpecState:
        return TlaSpecState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            task_id=payload.get("task_id", ""),
            current_score=payload.get("current_score", 0.0),
            max_steps=payload.get("max_steps", 5),
        )
