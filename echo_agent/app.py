"""
Echo Agent.

The goal of this agent is to implement an agent that can create new static
connections, receive messages, and send messages while minimizing logic and,
therefore (hopefully) how much code needs to be maintained.

Required operations include:
- create static connection
- receive message
- retrieve messages
- send message
"""

import asyncio
import logging
from typing import Dict, List, Optional
from uuid import uuid4

from aries_staticagent import (
    Connection,
    Message,
    Target,
    crypto,
)
from aries_staticagent.utils import ensure_key_b58
from fastapi import Body, FastAPI, HTTPException, Request

from pydantic.dataclasses import dataclass
from async_selective_queue import AsyncSelectiveQueue as Queue

from .session import Session, SessionMessage
from .models import (
    NewConnection,
    ConnectionInfo as ConnectionInfoModel,
    SessionInfo,
    Webhook as WebhookModel,
)


# Convert dataclasses to pydantic dataclasses
# See this issue for why this is necessary:
# https://github.com/tiangolo/fastapi/issues/5138
@dataclass
class ConnectionInfo(ConnectionInfoModel):
    pass


@dataclass
class Webhook(WebhookModel):
    pass


# Logging
LOGGER = logging.getLogger("uvicorn.error." + __name__)

# Global state
connections: Dict[str, Connection] = {}
sessions: Dict[str, Session] = {}
recip_key_to_connection_id: Dict[str, str] = {}
messages: Dict[str, Queue[Message]] = {}
webhooks: Queue[Webhook] = Queue()

# Defaults
TIMEOUT = 5

app = FastAPI(title="Echo Agent", version="0.1.0")


@app.on_event("startup")
async def setup_webhook_queue():
    webhooks._cond = asyncio.Condition()


@app.post("/connection", response_model=ConnectionInfo, operation_id="new_connection")
async def new_connection(new_connection: NewConnection):
    """Create a new static connection."""
    LOGGER.debug("Creating new connection from request: %s", new_connection)
    queue = Queue()
    try:
        conn = Connection.from_seed(
            seed=new_connection.seed.encode("ascii"),
            target=Target(
                endpoint=new_connection.endpoint,
                recipients=new_connection.recipient_keys,
                routing_keys=new_connection.routing_keys,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    # Type narrowing
    assert conn.target.recipients
    assert conn.target.endpoint

    # Store state
    connection_id = str(uuid4())
    connections[connection_id] = conn
    messages[connection_id] = queue
    recip_key_to_connection_id[conn.verkey_b58] = connection_id

    # Response
    result = ConnectionInfo(
        connection_id=connection_id,
        did=conn.did,
        verkey=conn.verkey_b58,
        endpoint=conn.target.endpoint,
        recipient_keys=[ensure_key_b58(recip) for recip in conn.target.recipients],
        routing_keys=[
            ensure_key_b58(route) for route in conn.target.routing_keys or []
        ],
    )
    LOGGER.debug("Returning new connection: %s", result)
    return result


@app.delete(
    "/connection/{connection_id}", response_model=str, operation_id="delete_connection"
)
async def delete_connection(connection_id: str):
    """Delete a connection."""
    if connection_id not in connections:
        raise HTTPException(
            status_code=404, detail=f"No connection id matching {connection_id}"
        )

    conn = connections.pop(connection_id)
    del messages[connection_id]
    del recip_key_to_connection_id[conn.verkey_b58]
    return connection_id


@app.get(
    "/connections", response_model=List[ConnectionInfo], operation_id="get_connections"
)
async def get_connections() -> List[ConnectionInfo]:
    return [
        ConnectionInfo(
            connection_id=connection_id,
            did=conn.did,
            verkey=conn.verkey_b58,
            endpoint=conn.target.endpoint or "",
            recipient_keys=[
                crypto.bytes_to_b58(key_bytes)
                for key_bytes in conn.target.recipients or []
            ],
            routing_keys=[
                crypto.bytes_to_b58(key_bytes)
                for key_bytes in conn.target.routing_keys or []
            ],
        )
        for connection_id, conn in connections.items()
    ]


@app.get(
    "/connection/{connection_id}",
    response_model=ConnectionInfo,
    operation_id="get_connection",
)
async def get_connection(connection_id: str) -> ConnectionInfo:
    """Get info for a connection."""
    conn = connections.get(connection_id)
    if not conn:
        raise HTTPException(
            status_code=404, detail=f"No connection id matching {connection_id}"
        )

    return ConnectionInfo(
        connection_id=connection_id,
        did=conn.did,
        verkey=conn.verkey_b58,
        endpoint=conn.target.endpoint or "",
        recipient_keys=[
            crypto.bytes_to_b58(key_bytes) for key_bytes in conn.target.recipients or []
        ],
        routing_keys=[
            crypto.bytes_to_b58(key_bytes)
            for key_bytes in conn.target.routing_keys or []
        ],
    )


async def handle_new_message(message: bytes):
    """Receive a new message."""
    LOGGER.debug("Message received: %s", message)
    handled = False
    for recipient in crypto.recipients_from_packed_message(message):
        if recipient in recip_key_to_connection_id:
            connection_id = recip_key_to_connection_id[recipient]
            LOGGER.debug(
                "Found connection %s for message recipient %s", connection_id, recipient
            )
            conn = connections[connection_id]
            queue = messages[connection_id]
            unpacked = conn.unpack(message)
            LOGGER.debug("Unpacked message: %s", unpacked)
            await queue.put(unpacked)
            handled = True
    if not handled:
        LOGGER.warning("Received message that could not be handled: %s", message)


@app.post("/")
@app.post("/message")
async def new_message(request: Request):
    """Receive a new agent message and push onto the message queue."""
    message = await request.body()
    return await handle_new_message(message)


@app.get(
    "/messages/{connection_id}",
    response_model=List[Message],
    operation_id="retrieve_messages",
)
async def get_messages(connection_id: str, session_id: Optional[str] = None):
    """Retrieve all received messages for recipient key."""
    if connection_id not in messages:
        raise HTTPException(
            status_code=404, detail=f"No connection id matching {connection_id}"
        )

    queue = messages[connection_id]
    if not session_id:
        LOGGER.debug("Retrieving messages for connection_id %s", connection_id)
        return queue.get_all()

    return queue.get_all(
        lambda msg: isinstance(msg, SessionMessage) and msg.session_id == session_id
    )


@app.get(
    "/message/{connection_id}", response_model=Message, operation_id="wait_for_message"
)
async def get_message(
    connection_id: str,
    thid: Optional[str] = None,
    msg_type: Optional[str] = None,
    wait: Optional[bool] = True,
    session_id: Optional[str] = None,
    timeout: int = TIMEOUT,
):
    """Wait for a message matching criteria."""

    def _condition(msg: Message):
        return all(
            [
                msg.thread["thid"] == thid if thid else True,
                msg.type == msg_type if msg_type else True,
                msg.session_id == session_id
                if isinstance(msg, SessionMessage) and session_id
                else True,
            ]
        )

    if connection_id not in messages:
        raise HTTPException(
            status_code=404, detail=f"No connection id matching {connection_id}"
        )

    queue = messages[connection_id]
    if wait:
        try:
            message = await queue.get(select=_condition, timeout=timeout)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail=(
                    f"No message found for connection id {connection_id} "
                    "before timeout"
                ),
            )
    else:
        message = queue.get_nowait(select=_condition)

    if not message:
        raise HTTPException(
            status_code=404,
            detail=f"No message found for connection id {connection_id}",
        )

    LOGGER.debug("Received message, returning to waiting client: %s", message)
    return message


@app.post("/message/{connection_id}", operation_id="send_message")
async def send_message(connection_id: str, message: dict = Body(...)):
    """Send a message to connection identified by connection ID."""
    LOGGER.debug("Sending message to %s: %s", connection_id, message)
    if connection_id not in connections:
        raise HTTPException(
            status_code=404, detail=f"No connection matching {connection_id} found"
        )
    conn = connections[connection_id]
    await conn.send_async(message)


@app.get(
    "/session/{connection_id}", operation_id="open_session", response_model=SessionInfo
)
async def open_session(connection_id: str, endpoint: Optional[str] = None):
    """Open a session."""
    if connection_id not in connections:
        raise HTTPException(
            status_code=404, detail=f"No connection matching {connection_id} found"
        )
    conn = connections[connection_id]

    session = Session(conn, handle_new_message, endpoint)
    sessions[session.id] = session
    session.open()
    return SessionInfo(session.id, connection_id)


@app.delete("/session/{session_id}")
async def close_session(session_id: str):
    """Close an open session."""
    if session_id not in sessions:
        raise HTTPException(
            status_code=404, detail=f"No session matching {session_id} found"
        )
    session = sessions[session_id]
    await session.close()
    sessions.pop(session_id)
    return session_id


@app.post("/message/session/{session_id}")
async def send_message_to_session(session_id: str, message: dict = Body(...)):
    """Send a message to a session identified by session ID."""
    if session_id not in sessions:
        raise HTTPException(
            status_code=404, detail=f"No session matching {session_id} found"
        )
    session = sessions[session_id]
    await session.send(message)


@app.post("/webhook/{topic:path}", response_model=Webhook)
async def receive_webhook(topic: str, payload: dict = Body(...)):
    """Receive a webhook."""
    LOGGER.debug("Received webhook: topic %s, payload %s", topic, payload)
    webhook = Webhook(topic, payload)
    await webhooks.put(webhook)
    return webhook


@app.get(
    "/webhooks",
    response_model=List[Webhook],
    operation_id="",
)
async def get_webhooks(topic: Optional[str] = None):
    """Retrieve all received messages for recipient key."""
    if not topic:
        LOGGER.debug("Retrieving webhooks")
        return webhooks.get_all()

    return webhooks.get_all(lambda entry: entry.topic == topic)


@app.get("/webhook", response_model=Webhook, operation_id="wait_for_webhook")
async def get_webhook(
    topic: Optional[str] = None,
    wait: Optional[bool] = True,
    timeout: int = TIMEOUT,
):
    """Wait for a message matching criteria."""

    def _condition(entry: Webhook):
        return entry.topic == topic if topic else True

    if wait:
        try:
            webhook = await webhooks.get(select=_condition, timeout=timeout)
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=408,
                detail=("No webhook found before timeout"),
            )
    else:
        webhook = webhooks.get_nowait(select=_condition)

    if not webhook:
        raise HTTPException(
            status_code=404,
            detail="No webhook found",
        )

    LOGGER.debug("Received webhook, returning to waiting client: %s", webhook)
    return webhook


__all__ = ["app"]
