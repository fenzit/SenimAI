import json
from pathlib import Path
import pytest
from app.schemas.analysis import AnalyzeRequest
from app.services.analyzer import Analyzer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    with open(FIXTURES_DIR / f"{name}.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize(
    "fixture_name",
    [
        "fully_correct",
        "obvious_hallucination",
        "partially_correct",
        "opinion",
        "conflicting_sources",
        "temporal_claim",
    ],
)
def test_fixtures_load(fixture_name):
    data = load_fixture(fixture_name)
    assert "input" in data
    assert "expected" in data
    assert len(data["input"]["text"]) > 0


@pytest.mark.asyncio
async def test_mock_analyzer_on_fixtures():
    data = load_fixture("obvious_hallucination")
    analyzer = Analyzer()
    req = AnalyzeRequest(
        text=data["input"]["text"],
        language=data["input"].get("language", "ru"),
    )
    res = await analyzer.analyze(req)
    assert res.summary.total_claims >= 1
    assert len(res.claims) >= 1
    for c in res.claims:
        assert c.verdict is not None
        assert c.confidence >= 0.0
