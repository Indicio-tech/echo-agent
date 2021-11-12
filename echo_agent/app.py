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

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from aries_staticagent import (
    Connection,
    Message,
    MsgQueue,
    QueueDispatcher,
    Target,
    crypto,
)
from fastapi import Body, FastAPI, HTTPException, Request
from .models import NewConnection, ConnectionInfo

# Logging
LOGGER = logging.getLogger("uvicorn.error." + __name__)

# Global state
connections: Dict[str, Connection] = {}
sessions: Dict[str, Any] = {}
recip_key_to_connection_id: Dict[str, str] = {}
messages: Dict[str, MsgQueue] = {}


app = FastAPI(title="Echo Agent", version="0.1.0")


class SessionMessage(Message):
    pass


@app.post("/connection", response_model=ConnectionInfo, operation_id="new_connection")
async def new_connection(new_connection: NewConnection):
    """Create a new static connection."""
    LOGGER.debug("Creating new connection from request: %s", new_connection)
    dispatcher = QueueDispatcher()
    conn = Connection.from_seed(
        seed=new_connection.seed.encode("ascii"),
        target=Target(
            endpoint=new_connection.endpoint, their_vk=new_connection.their_vk
        ),
        dispatcher=dispatcher,
    )

    # Store state
    connection_id = str(uuid4())
    connections[connection_id] = conn
    messages[connection_id] = dispatcher.queue
    recip_key_to_connection_id[conn.verkey_b58] = connection_id

    # Response
    result = ConnectionInfo(
        connection_id=connection_id,
        did=conn.did,
        verkey=conn.verkey_b58,
        their_vk=new_connection.their_vk,
        endpoint=new_connection.endpoint,
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
            their_vk=crypto.bytes_to_b58(conn.target.recipients[0]),
            endpoint=conn.target.endpoint,
        )
        for connection_id, conn in connections.items()
        if conn.target and conn.target.recipients
    ]


@app.post("/")
@app.post("/message")
async def new_message(request: Request):
    """Receive a new agent message and push onto the message queue."""
    message = await request.body()
    LOGGER.debug("Message received: %s", message)
    handled = False
    for recipient in crypto.recipients_from_packed_message(message):
        if recipient in recip_key_to_connection_id:
            connection_id = recip_key_to_connection_id[recipient]
            LOGGER.debug(
                "Found connection %s for message recipient %s", connection_id, recipient
            )
            conn = connections[connection_id]
            unpacked = conn.unpack(message)
            LOGGER.debug("Unpacked message: %s", unpacked)
            await conn.dispatch(unpacked)
            handled = True
    if not handled:
        LOGGER.warning("Received message that could not be handled: %s", message)


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

    if not session_id:
        LOGGER.debug("Retrieving messages for connection_id %s", connection_id)
        queue = messages[connection_id]
        return await queue.flush()

    # TODO loop with get_nowait until returns a None with condition matching session ID
    return []


@app.get(
    "/message/{connection_id}", response_model=Message, operation_id="wait_for_message"
)
async def get_message(
    connection_id: str,
    thid: Optional[str] = None,
    msg_type: Optional[str] = None,
    wait: Optional[bool] = True,
    session_id: Optional[str] = None,
):
    """Wait for a message matching criteria."""

    def _thid_match(msg: Message):
        return msg.thread["thid"] == thid

    def _msg_type_match(msg: Message):
        return msg.type == msg_type

    def _thid_and_msg_type_match(msg: Message):
        return _thid_match(msg) and _msg_type_match(msg)

    def _session_id_match(msg: Message):
        return isinstance(msg, SessionMessage) and msg.session_id == session_id

    # TODO combinations of the above conditions without having to define
    # separate functions?

    condition = None
    if thid is not None:
        condition = _thid_match
    if msg_type is not None:
        condition = _msg_type_match
    if thid is not None and msg_type is not None:
        condition = _thid_and_msg_type_match

    if connection_id not in messages:
        raise HTTPException(
            status_code=404, detail=f"No connection id matching {connection_id}"
        )

    queue = messages[connection_id]
    if wait:
        message = await queue.get(condition=condition)
    else:
        message = queue.get_nowait(condition=condition)

    if not message:
        raise HTTPException(
            status_code=404,
            detail=f"No message found for connection id {connection_id}",
        )

    LOGGER.debug("Received message, returning to waiting client: %s", message)
    return message


@app.post("/message/{connection_id}", operation_id="send_message")
async def send_message(connection_id: str, message: dict = Body(...)):
    """Send a message to connection identified by did."""
    LOGGER.debug("Sending message to %s: %s", connection_id, message)
    if connection_id not in connections:
        raise HTTPException(
            status_code=404, detail=f"No connection matching {connection_id} found"
        )
    conn = connections[connection_id]
    await conn.send_async(message)


@app.get("/session/{connection_id}")
async def open_session(connection_id: str, endpoint: Optional[str] = None):
    pass


@app.delete("/session/{session_id}")
async def close_session(session_id: str):
    pass


@app.post("/message/session/{session_id}")
async def send_message_to_session(session_id: str):
    pass


__all__ = ["app"]
