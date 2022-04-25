import pytest
from echo_agent import EchoClient


@pytest.fixture
async def echo_client():
    from echo_agent import app

    yield EchoClient(base_url="http://test", app=app)
