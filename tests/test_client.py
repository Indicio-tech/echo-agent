from aries_staticagent.dispatcher.queue_dispatcher import QueueDispatcher
from echo_agent.models import ConnectionInfo
from uuid import uuid4
import pytest
from echo_agent.client import EchoClient, NoOpenClient
from echo_agent.app import messages, connections, recip_key_to_connection_id
from aries_staticagent import Connection, Target, crypto


@pytest.fixture(autouse=True)
def clear_app_state():
    yield
    connections.clear()
    messages.clear()


@pytest.fixture
def target():
    vk, _ = crypto.create_keypair()
    yield Target(their_vk=vk, endpoint="test")


@pytest.fixture
def test_conn(target):
    dispatcher = QueueDispatcher()
    conn = Connection.random(target=target, dispatcher=dispatcher)
    connection_id = str(uuid4())
    connections[connection_id] = conn
    messages[connection_id] = dispatcher.queue
    recip_key_to_connection_id[conn.verkey_b58] = connection_id
    yield connection_id, conn


@pytest.fixture
def conn(test_conn):
    yield test_conn[1]


@pytest.fixture
def connection_id(test_conn):
    yield test_conn[0]


@pytest.fixture
def conn_info(connection_id, conn, target):
    yield ConnectionInfo(
        connection_id=connection_id,
        did=conn.did,
        verkey=conn.verkey_b58,
        their_vk=crypto.bytes_to_b58(target.recipients[0]),
        endpoint=target.endpoint,
    )


@pytest.mark.asyncio
async def test_new_conn_x_not_open(echo_client: EchoClient):
    with pytest.raises(NoOpenClient):
        await echo_client.new_connection(seed="test", endpoint="test", their_vk="test")


@pytest.mark.asyncio
async def test_new_conn(echo_client: EchoClient):
    async with echo_client:
        conn = await echo_client.new_connection(
            seed="test0000000000000000000000000000", endpoint="test", their_vk="test"
        )
        assert conn.connection_id in connections


@pytest.mark.asyncio
async def test_get_conns(echo_client: EchoClient, conn_info):
    async with echo_client:
        connections = await echo_client.get_connections()
        assert conn_info in connections


@pytest.mark.asyncio
async def test_delete_connection(echo_client: EchoClient, connection_id: str):
    async with echo_client:
        await echo_client.delete_connection(connection_id)
        assert connection_id not in connections
