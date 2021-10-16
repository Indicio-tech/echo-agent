import pytest
from echo_agent import app, EchoClient


@pytest.fixture
def echo_client():
    yield EchoClient(base_url="http://test", app=app)
