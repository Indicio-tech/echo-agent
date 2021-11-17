import asyncio
from uuid import uuid4

from aries_staticagent import Connection, Target, crypto
from aries_staticagent.dispatcher.queue_dispatcher import QueueDispatcher
from aries_staticagent.message import Message
import pytest

from echo_agent.app import connections, messages, recip_key_to_connection_id
from echo_agent.client import EchoClient, NoOpenClient
from echo_agent.models import ConnectionInfo
from echo_agent.session import SessionMessage


@pytest.fixture(autouse=True)
def clear_app_state():
    yield
    connections.clear()
    messages.clear()


@pytest.fixture
def recip():
    yield Connection.random()


@pytest.fixture
def target(recip: Connection):
    yield Target(their_vk=recip.verkey, endpoint="test")


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


@pytest.mark.asyncio
async def test_receive_message(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = Message.parse_obj({"@type": "doc/protocol/1.0/message"})
    async with echo_client:
        await echo_client.new_message(recip.pack(msg))
    assert messages[connection_id]._queue


@pytest.mark.asyncio
async def test_get_messages(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = Message.parse_obj({"@type": "doc/protocol/1.0/message"})
    async with echo_client:
        await echo_client.new_message(recip.pack(msg))
        messages = await echo_client.get_messages(connection_id)
    assert messages


@pytest.mark.asyncio
async def test_get_messages_session(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = SessionMessage.from_message(
        "test_session_id", Message.parse_obj({"@type": "doc/protocol/1.0/message"})
    )
    await messages[connection_id].put(msg)
    async with echo_client:
        retrieved_messages = await echo_client.get_messages(
            connection_id, "test_session_id"
        )
    assert retrieved_messages


@pytest.mark.asyncio
async def test_get_message_post(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = Message.parse_obj({"@type": "doc/protocol/1.0/message"})
    async with echo_client:
        await echo_client.new_message(recip.pack(msg))
        message = await echo_client.get_message(connection_id)
    assert message


@pytest.mark.asyncio
async def test_get_message_post_condition(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = SessionMessage.from_message(
        "test_session_id",
        Message.parse_obj(
            {"@type": "doc/protocol/1.0/message", "~thread": {"thid": "test_id"}}
        ),
    )
    await messages[connection_id].put(msg)
    async with echo_client:
        message = await echo_client.get_message(
            connection_id,
            msg_type="doc/protocol/1.0/message",
            thid="test_id",
            session="test_session_id",
        )
    assert message


@pytest.mark.asyncio
async def test_get_message_pre(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = Message.parse_obj({"@type": "doc/protocol/1.0/message"})

    async def _produce(echo_client):
        await asyncio.sleep(0.5)
        await echo_client.new_message(recip.pack(msg))

    async def _consume(echo_client):
        return await echo_client.get_message(connection_id)

    async with echo_client:
        _, message = await asyncio.gather(_produce(echo_client), _consume(echo_client))
    assert message


@pytest.mark.asyncio
async def test_get_message_no_wait(
    echo_client: EchoClient, recip: Connection, conn: Connection, connection_id: str
):
    """Test reception of a message."""
    recip.target = Target(their_vk=conn.verkey, endpoint="test")
    msg = Message.parse_obj({"@type": "doc/protocol/1.0/message"})
    async with echo_client:
        await echo_client.new_message(recip.pack(msg))
        message = await echo_client.get_message(connection_id, wait=False)
    assert message
