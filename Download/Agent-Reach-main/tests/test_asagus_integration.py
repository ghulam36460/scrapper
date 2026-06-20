# -*- coding: utf-8 -*-
"""Tests for the native ASAGUS co-engine integration."""

import sys
from pathlib import Path

from agent_reach.integrations.asagus import (
    AsagusCoEngine,
    AsagusJobContext,
    ensure_asagus_backend_dependencies,
)


def test_asagus_dry_run_writes_metadata(tmp_path):
    context = AsagusJobContext(
        job_id="unit-job",
        query="audit firms",
        location="Qatar",
        real_run=False,
        runs_root=tmp_path,
        output_dir=tmp_path / "unit-job",
        dependency_bootstrap=False,
    )

    result = AsagusCoEngine(context, bootstrap_dependencies=False).run()

    assert result["status"] == "dry_run"
    assert result["integration_level"] == "agent_reach_native_asagus_co_engine"
    assert Path(result["job_context"]["output_dir"]).exists()
    assert (tmp_path / "unit-job" / "agent-reach.json").exists()


def test_asagus_status_includes_manifest(tmp_path):
    context = AsagusJobContext(
        job_id="unit-status",
        query="audit firms",
        runs_root=tmp_path,
        output_dir=tmp_path / "unit-status",
        dependency_bootstrap=False,
    )

    status = AsagusCoEngine(context, bootstrap_dependencies=False).status()

    assert status["integration_config"]["entry_module"] == "agent_reach.integrations.asagus"
    assert "dependency_status" in status
    assert "channels_status" in status


def test_dependency_probe_can_run_without_installing():
    status = ensure_asagus_backend_dependencies(
        backend_python=Path(sys.executable),
        auto_install=False,
    )

    assert status["backend_python"] == str(Path(sys.executable).absolute())
    assert status["auto_install"] is False
    assert "dependencies_checked" in status
    assert "missing_after" in status
