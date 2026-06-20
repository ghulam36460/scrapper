"""
Compatibility entry point for older Agent Reach integration scripts.

The production implementation now lives in asagus_adapter.py so the MAX-mode
launcher, run-asagus.sh, and any direct calls share one code path.
"""
from __future__ import annotations

from asagus_adapter import AgentReachAdapter, main

__all__ = ["AgentReachAdapter", "main"]


if __name__ == "__main__":
    main()
