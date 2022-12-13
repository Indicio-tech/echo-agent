"""Client to Echo Agent."""
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Sequence, Union

from httpx import AsyncClient

from .models import ConnectionInfo, NewConnection, SessionInfo, Webhook


class EchoClientError(Exception):
    """General echo client error."""


class NoOpenClient(EchoClientError):
    """Raised when no client is open."""


class EchoClient(AbstractAsyncContextManager):
    """Interact with a remote echo agent."""

    def __init__(self, base_url: str, **kwargs):
        """Initialize the echo client."""
        self.base_url = base_url
        self.client: Optional[AsyncClient] = None
        self.active: int = 0
        self.options = kwargs

    async def __aenter__(self):
        """Start the client."""
        self.active += 1
        self.client = AsyncClient(base_url=self.base_url, **self.options)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Stop the client."""
        self.active -= 1
        if self.active < 1 and self.client:
            await self.client.__aexit__(exc_type, exc_value, traceback)

    async def new_connection(
        self,
        seed: str,
        endpoint: str,
        recipient_keys: Optional[Sequence[str]] = None,
        routing_keys: Optional[Sequence[str]] = None,
    ) -> ConnectionInfo:
        """Create a new connection."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post(
            "/connection",
            json=asdict(
                NewConnection(
                    seed=seed,
                    endpoint=endpoint,
                    recipient_keys=recipient_keys or [],
                    routing_keys=routing_keys or [],
                )
            ),
        )

        if response.is_error:
            raise EchoClientError(
                f"Failed to create new connection: {response.content}"
            )

        return ConnectionInfo(**response.json())

    async def delete_connection(self, connection: Union[str, ConnectionInfo]) -> str:
        """Remove a connection."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        response = await self.client.delete(f"/connection/{connection_id}")

        if response.is_error:
            raise EchoClientError("Failed to send message")

        return response.content.decode()

    async def get_connections(self) -> List[ConnectionInfo]:
        """Get all connections."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )
        response = await self.client.get("/connections")
        if response.is_error:
            raise EchoClientError("Failed to retrieve connections")
        return [ConnectionInfo(**info) for info in response.json()]

    async def new_message(self, packed_message: bytes):
        """Post a new message to the echo agent."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post("/", content=packed_message)

        if response.is_error:
            raise EchoClientError("Failed to receive message")

    async def get_messages(
        self,
        connection: Union[str, ConnectionInfo],
        session: Union[str, SessionInfo, None] = None,
    ) -> List[Mapping[str, Any]]:
        """Get all messages for a connection."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        session_id = (
            session
            if isinstance(session, str)
            else session.session_id
            if isinstance(session, SessionInfo)
            else None
        )
        response = await self.client.get(
            f"/messages/{connection_id}",
            params={"session_id": session_id} if session_id else {},
        )

        if response.is_error:
            raise EchoClientError(f"Failed to retrieve messages: {response.content}")

        return response.json()

    async def get_message(
        self,
        connection: Union[str, ConnectionInfo],
        *,
        thid: Optional[str] = None,
        msg_type: Optional[str] = None,
        session: Optional[Union[str, SessionInfo]] = None,
        wait: Optional[bool] = True,
        timeout: Optional[int] = None,
    ) -> Mapping[str, Any]:
        """Get a message matching criteria."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        session_id = (
            session
            if isinstance(session, str)
            else session.session_id
            if isinstance(session, SessionInfo)
            else None
        )
        response = await self.client.get(
            f"/message/{connection_id}",
            params={
                k: v
                for k, v in {
                    "thid": thid,
                    "msg_type": msg_type,
                    "session_id": session_id,
                    "wait": wait,
                    "timeout": timeout,
                }.items()
                if v is not None
            },
        )

        if response.is_error:
            raise EchoClientError(f"Failed to wait for message: {response.content}")

        return response.json()

    async def send_message(
        self,
        connection: Union[str, ConnectionInfo],
        message: Mapping[str, Any],
    ):
        """Send a message to a connection."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        response = await self.client.post(f"/message/{connection_id}", json=message)

        if response.is_error:
            raise EchoClientError(f"Failed to send message: {response.content}")

    @asynccontextmanager
    async def session(
        self, connection: Union[str, ConnectionInfo], endpoint: Optional[str] = None
    ) -> AsyncIterator["ClientSession"]:
        """Open a session."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        session_info: Optional[SessionInfo] = None
        try:
            response = await self.client.get(
                f"/session/{connection_id}",
                params={"endpoint": endpoint} if endpoint else {},
            )
            if response.is_error:
                raise EchoClientError(f"Failed to open session: {response.content}")
            session_info = ClientSession(echo=self, **response.json())
            yield session_info
        finally:
            if session_info:
                await self.client.delete(f"/session/{session_info.session_id}")

    async def send_message_to_session(
        self, session: Union[str, SessionInfo], message: Mapping[str, Any]
    ):
        """Send a message to the session."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        session_id = session if isinstance(session, str) else session.session_id
        response = await self.client.post(
            f"/message/session/{session_id}", json=message
        )

        if response.is_error:
            raise EchoClientError(f"Failed to send message: {response.content}")

    async def new_webhook(self, topic: str, payload: Dict[str, Any]):
        """Post a new webhook to the echo agent."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post(f"/webhook/{topic}", json=payload)

        if response.is_error:
            raise EchoClientError("Failed to receive webhook")

    async def get_webhooks(
        self,
        *,
        topic: Optional[str] = None,
    ) -> List[Webhook]:
        """Get all messages, optionally matching topic."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.get(
            "/webhooks",
            params={"topic": topic} if topic else {},
        )

        if response.is_error:
            raise EchoClientError(f"Failed to retrieve webhooks: {response.content}")

        return response.json()

    async def get_webhook(
        self,
        *,
        topic: Optional[str] = None,
        wait: Optional[bool] = True,
        timeout: Optional[int] = None,
    ) -> Mapping[str, Any]:
        """Get a webhook matching criteria."""
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.get(
            "/webhook",
            params={
                k: v
                for k, v in {
                    "topic": topic,
                    "wait": wait,
                    "timeout": timeout,
                }.items()
                if v is not None
            },
        )

        if response.is_error:
            raise EchoClientError(f"Failed to wait for webhook: {response.content}")

        return response.json()


@dataclass
class ClientSession(SessionInfo):
    """Client session for easily sending and retrieving session messages."""

    def __init__(self, session_id: str, connection_id: str, *, echo: EchoClient):
        """Initialize client session."""
        super().__init__(session_id, connection_id)
        self.echo = echo

    async def send_message(self, message: Mapping[str, Any]):
        """Send message to this session."""
        return await self.echo.send_message_to_session(self.session_id, message)

    async def get_messages(self) -> List[Mapping[str, Any]]:
        """Get all messages for this session."""
        return await self.echo.get_messages(self.connection_id, self.session_id)

    async def get_message(
        self,
        *,
        connection: Optional[Union[str, ConnectionInfo]] = None,
        thid: Optional[str] = None,
        msg_type: Optional[str] = None,
        wait: Optional[bool] = True,
        timeout: Optional[int] = None,
    ) -> Mapping[str, Any]:
        """Get message for session."""
        return await self.echo.get_message(
            connection or self.connection_id,
            session=self.session_id,
            thid=thid,
            msg_type=msg_type,
            wait=wait,
            timeout=timeout,
        )
