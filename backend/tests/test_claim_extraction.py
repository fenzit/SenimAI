import pytest
from app.providers.llm import MockLLMProvider
from app.schemas.claim import ClaimType
from app.services.claim_extractor import ClaimExtractor


@pytest.mark.asyncio
async def test_claim_extraction_with_mock():
    mock_llm = MockLLMProvider()
    extractor = ClaimExtractor(llm=mock_llm)

    text = "Python был создан Гвидо ван Россумом в 1991 году."
    claims = await extractor.extract(text=text, max_claims=5)

    assert len(claims) >= 1
    assert claims[0].id == 1
    assert claims[0].text != ""
    assert isinstance(claims[0].type, ClaimType)


def test_fallback_claim_extraction():
    extractor = ClaimExtractor(llm=MockLLMProvider())
    text = "Первое предложение о факте номер один. Второе предложение о факте номер два."
    claims = extractor._fallback_extract(text=text, max_claims=5)

    assert len(claims) == 2
    assert "Первое предложение" in claims[0].text
    assert "Второе предложение" in claims[1].text
