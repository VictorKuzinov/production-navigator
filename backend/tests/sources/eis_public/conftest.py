"""Shared fixtures for EIS public adapter tests."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "eis_public"


@pytest.fixture()
def sample_html_path() -> Path:
    return FIXTURES_DIR / "notice_44fz_sample.html"


@pytest.fixture()
def sample_html(sample_html_path: Path) -> str:
    return sample_html_path.read_text(encoding="utf-8")
