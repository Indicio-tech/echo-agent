"""Session."""
import asyncio
from contextlib import suppress
import logging
from uuid import uuid4
import aiohttp
from typing import Optional, Union
from aries_staticagent import Message, Connection


# Logging
LOGGER = logging.getLogger("uvicorn.error." + __name__)


class SocketClosed(Exception):
    """Raised when socket is not open."""


class SessionMessage(Message):
    session_id: str

    @classmethod
    def from_message(cls, session_id: str, msg: Message):
        """Create a SessionMessage from a Message."""
        return cls(session_id=session_id, **msg.dict(by_alias=True, exclude_none=True))


class Session:
    """Session object."""

    def __init__(self, connection: Connection, endpoint: Optional[str] = None):
        self.id = str(uuid4())
        self.connection = connection

        if endpoint:
            self.endpoint = endpoint
        elif not endpoint and connection.target and connection.target.endpoint:
            self.endpoint = connection.target.endpoint
        else:
            raise ValueError(
                "Endpoint must be specified or target must be present in connection"
            )

        self._task: Optional[asyncio.Future] = None
        self.socket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._opened: asyncio.Event = asyncio.Event()

    async def _open(self):
        LOGGER.debug("Starting session to %s", self.endpoint)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.ws_connect(self.endpoint) as socket:
                    LOGGER.debug("Socket connected to %s", self.endpoint)
                    self.socket = socket
                    self._opened.set()
                    async for msg in socket:
                        LOGGER.debug("Received ws message: %s", msg)
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            unpacked = self.connection.unpack(msg.data)
                            LOGGER.debug(
                                "Unpacked message from websocket: %s",
                                unpacked.pretty_print(),
                            )
                            await self.connection.dispatch(
                                SessionMessage.from_message(self.id, unpacked)
                            )
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            LOGGER.error(
                                "ws connection closed with exception %s",
                                socket.exception(),
                            )
            except Exception:
                LOGGER.exception("Websocket connection error")
        self.socket = None

    def open(self):
        """Open the session."""
        self._task = asyncio.ensure_future(self._open())

    async def close(self):
        """Stop the session."""
        if self.socket:
            await self.socket.close()
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._opened.clear()

    async def send(self, msg: Union[dict, Message]):
        if not self.socket:
            if self._task:
                await self._opened.wait()
            else:
                raise SocketClosed("No open socket to send message")
        if not self.socket:
            raise SocketClosed("No open socket even after waiting for open")

        packed = self.connection.pack(msg)
        await self.socket.send_bytes(packed)
