import pytest
from echo_agent import EchoClient
from echo_agent.app import webhooks


@pytest.fixture
async def echo_client():
    from echo_agent import app

    await webhooks.setup()
    yield EchoClient(base_url="http://test", app=app)
