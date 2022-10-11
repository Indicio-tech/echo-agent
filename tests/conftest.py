import pytest
from echo_agent import EchoClient
from echo_agent.app import setup_webhook_queue


@pytest.fixture
async def echo_client():
    from echo_agent import app

    await setup_webhook_queue()
    yield EchoClient(base_url="http://test", app=app)
