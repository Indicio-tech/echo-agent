"""Client to Echo Agent."""
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict
from typing import Any, List, Mapping, Optional, Union

from httpx import AsyncClient

from .models import ConnectionInfo, NewConnection, SessionInfo


class EchoClientError(Exception):
    """General echo client error."""


class NoOpenClient(EchoClientError):
    """Raised when no client is open."""


class EchoClient(AbstractAsyncContextManager):
    """Interact with a remote echo agent."""

    def __init__(self, base_url: str, **kwargs):
        self.base_url = base_url
        self.client: Optional[AsyncClient] = None
        self.active: int = 0
        self.options = kwargs

    async def __aenter__(self):
        self.active += 1
        self.client = AsyncClient(base_url=self.base_url, **self.options)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.active -= 1
        if self.active < 1 and self.client:
            await self.client.__aexit__(exc_type, exc_value, traceback)

    async def new_connection(
        self, seed: str, endpoint: str, their_vk: str
    ) -> ConnectionInfo:
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post(
            "/connection",
            json=asdict(NewConnection(seed=seed, endpoint=endpoint, their_vk=their_vk)),
        )

        if response.is_error:
            raise EchoClientError(
                f"Failed to create new connection: {response.content}"
            )

        return ConnectionInfo(**response.json())

    async def delete_connection(self, connection: Union[str, ConnectionInfo]) -> str:
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
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )
        response = await self.client.get("/connections")
        if response.is_error:
            raise EchoClientError("Failed to retrieve connections")
        return [ConnectionInfo(**info) for info in response.json()]

    async def new_message(self, packed_message: bytes):
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
        timeout: Optional[int] = 5,
    ) -> Mapping[str, Any]:
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
    async def session(self, connection: Union[str, ConnectionInfo]):
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
            response = await self.client.get(f"/session/{connection_id}")
            if response.is_error:
                raise EchoClientError(f"Failed to open session: {response.content}")
            session_info = response.json()
            if not session_info:
                raise EchoClientError(
                    f"Could not determine session from: {response.content}"
                )
            yield session_info
        finally:
            if session_info:
                await self.client.delete(f"/session/{session_info.session_id}")

    async def send_message_to_session(
        self, session: Union[str, SessionInfo], message: Mapping[str, Any]
    ):
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
