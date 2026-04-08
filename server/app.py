"""
FastAPI application for the TLA+ Specification Verification Environment.
"""

import os
import sys

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError(
        "openenv is required. Install: pip install openenv-core"
    ) from e

# Handle imports for all execution modes (docker, uv run, python -m, openenv serve)
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    from models import TlaSpecAction, TlaSpecObservation
except ImportError:
    from tla_env.models import TlaSpecAction, TlaSpecObservation

try:
    from server.tla_env_environment import TlaEnvironment
except ImportError:
    from tla_env.server.tla_env_environment import TlaEnvironment

app = create_app(
    TlaEnvironment,
    TlaSpecAction,
    TlaSpecObservation,
    env_name="tla_env",
    max_concurrent_envs=4,
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for uv run / python -m."""
    import uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        ws_ping_interval=60,
        ws_ping_timeout=120,
    )


if __name__ == "__main__":
    main()
