from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "evals" / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES
