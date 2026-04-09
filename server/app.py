# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""FastAPI application for the Legacygym modernization environment."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

try:
    from ..models import LegacygymAction, LegacygymObservation
    from .environment import LegacygymEnvironment
except ImportError:
    from models import LegacygymAction, LegacygymObservation
    from server.environment import LegacygymEnvironment


app = create_app(
    LegacygymEnvironment,
    LegacygymAction,
    LegacygymObservation,
    env_name="legacygym",
    max_concurrent_envs=4,
)


def main(host: str | None = None, port: int | None = None):
    """Run the development server."""

    import argparse
    import uvicorn

    if host is None and port is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--port", type=int, default=8000)
        args = parser.parse_args()
        host = args.host
        port = args.port

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
