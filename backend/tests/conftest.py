"""Fixtures e helpers compartilhados entre testes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

PPD_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[2]
    / "planilhas-exemplos"
    / "19_PPD_MC_OR_R01-Nivel-1-2-Marco2026-14-05-2026.xlsm"
)

requires_ppd_example = pytest.mark.skipif(
    not PPD_EXAMPLE_PATH.is_file(),
    reason=f"planilha exemplo ausente: {PPD_EXAMPLE_PATH.name}",
)


@pytest.fixture
def no_vram_downgrade():
    """Evita troca de modelo por VRAM limitada (~8 GB) em CI/WSL."""

    def _passthrough(model, fallbacks=None, **kwargs):
        fb = [m for m in (fallbacks or []) if m and m != model]
        return model, fb, None

    with patch("core.runtime.model_vram.fit_model_to_vram", side_effect=_passthrough):
        yield
