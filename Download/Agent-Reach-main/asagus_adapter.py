"""ASAGUS launcher compatibility shim for Agent Reach.

The production ASAGUS co-engine lives in ``agent_reach.integrations.asagus``.
This file stays small because ``Download/asagus_tool_launcher.py`` imports
``AgentReachAdapter`` from here for every Download tool.
"""

from __future__ import annotations

import json

from agent_reach.integrations.asagus import run_from_environment


class AgentReachAdapter:
    """Compatibility class used by the generic ASAGUS Download launcher."""

    def run(self) -> dict:
        return run_from_environment()


def main() -> None:
    print(json.dumps(AgentReachAdapter().run(), ensure_ascii=False))


if __name__ == "__main__":
    main()
