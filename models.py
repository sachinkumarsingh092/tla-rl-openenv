"""
Data models for the TLA+ Specification Verification Environment.

The agent writes/fixes TLA+ specifications. The environment validates them
using SANY (syntax) and TLC (model checking).
"""

from typing import List, Optional

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


class TlaSpecAction(Action):
    """Agent submits a complete TLA+ specification."""

    spec_text: str = Field(..., description="Complete TLA+ specification text")


class TlaSpecObservation(Observation):
    """Observation returned after each step."""

    task_id: str = Field(default="", description="Active task identifier")
    task_description: str = Field(default="", description="What the agent must do")
    current_spec: str = Field(
        default="", description="Starting/current TLA+ spec (for fix/complete tasks)"
    )
    feedback: str = Field(
        default="", description="Error messages or verification results"
    )
    score: float = Field(
        default=0.01, description="Best score so far, strictly in (0, 1)"
    )
    attempts_remaining: int = Field(default=0, description="Steps left in episode")
    available_tasks: Optional[List[str]] = Field(
        default=None, description="Task IDs available (shown on initial reset)"
    )


class TlaSpecState(State):
    """Episode state tracking."""

    task_id: str = ""
    current_score: float = 0.01
    max_steps: int = 5
