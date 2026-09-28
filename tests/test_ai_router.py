from ai.mock_provider import MockAIProvider
from ai.router import AIRouter


def test_router_usa_il_provider():
    provider = MockAIProvider()
    router = AIRouter(provider)

    risposta = router.generate_response("Ciao")

    assert risposta == "Risposta simulata a: Ciao"