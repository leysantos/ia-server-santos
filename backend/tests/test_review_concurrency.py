"""Testes — revisão técnica vs análise visual concorrente."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from core.project_review.ingestion_pipeline import IngestionPipeline
from core.runtime.review_guard import assert_review_can_start


def test_assert_review_blocks_active_vision_on_same_project():
    registry = MagicMock()
    registry.list_jobs.return_value = [
        {
            "kind": "vision",
            "project_id": "proj-1",
            "label": "Análise visual (pci)",
        }
    ]
    with patch("core.runtime.review_guard.get_job_registry", return_value=registry):
        with pytest.raises(HTTPException) as exc:
            assert_review_can_start("proj-1")
        assert exc.value.status_code == 409


def test_assert_review_allows_when_no_vision_job():
    registry = MagicMock()
    registry.list_jobs.return_value = []
    with patch("core.runtime.review_guard.get_job_registry", return_value=registry):
        assert_review_can_start("proj-1")


def test_ingestion_reuses_cached_vision_json(tmp_path):
    pdf = tmp_path / "planta.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    cached = {
        "filename": "planta.pdf",
        "analysis": {"disciplina": "pci", "resumo_tecnico": "cache ok"},
        "model_used": "gemma3:12b",
    }

    pipeline = IngestionPipeline(enable_vision=True)
    with patch.object(pipeline.vision, "analyze_file") as mock_analyze:
        result = pipeline.process_file(
            pdf,
            existing_vision_json=cached,
        )
        mock_analyze.assert_not_called()
        assert result["vision_json"] == cached


def test_benchmark_cache_returns_cached_flag():
    from core.system.benchmark import collect_system_benchmark

    first = collect_system_benchmark(use_cache=True)
    second = collect_system_benchmark(use_cache=True)
    assert first.get("available") == second.get("available")
    assert second.get("cached") is True


def test_benchmark_includes_vram_metric():
    from core.system.benchmark import collect_system_benchmark

    with patch("core.system.benchmark._read_gpu_stats") as mock_gpu:
        mock_gpu.return_value = {
            "available": True,
            "percent": 42.0,
            "memory_percent": 75.5,
            "memory_used_mb": 6040.0,
            "memory_total_mb": 8192.0,
        }
        result = collect_system_benchmark(use_cache=False)

    assert result["vram"]["available"] is True
    assert result["vram"]["percent"] == 75.5
    assert result["vram"]["used_mb"] == 6040.0
    assert result["vram"]["total_mb"] == 8192.0
    assert result["gpu"]["percent"] == 42.0


def test_track_sync_job_context_manager():
    from core.runtime.job_tracking import track_sync_job

    with track_sync_job(kind="review", label="Teste revisão") as job:
        assert job.id
        job.update(phase="test", message="ok")
