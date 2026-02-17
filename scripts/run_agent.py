#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.services.agent_registry import BY_ID
from api.services.agent_runtime import run_agent_session
from api.services.session_manager import session_manager


async def _run(agent_id: str) -> None:
    session = await session_manager.create(agent_id)
    try:
        result = await run_agent_session(agent_id, session.session_id)
    except Exception as exc:
        print(f"Run failed: {exc}")
        raise SystemExit(1)

    print(f"Session: {session.session_id}")
    print(f"Agent: {agent_id}")
    print(f"Cost: ${result.total_cost:.6f}")
    print(f"Tokens: input={result.input_tokens}, output={result.output_tokens}")
    print("Output:")
    print(json.dumps(result.output, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an RPMX demo agent from CLI")
    parser.add_argument("agent_id", choices=sorted(BY_ID.keys()))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(_run(args.agent_id))


if __name__ == "__main__":
    main()
