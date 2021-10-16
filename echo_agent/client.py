"""Client to Echo Agent."""
from typing import Any, Dict, List, Optional, Union
from aries_staticagent.message import Message
from httpx import AsyncClient
from pydantic.tools import parse_obj_as
from contextlib import AbstractAsyncContextManager

from .models import ConnectionInfo, NewConnection


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
        self, seed: Union[str, bytes], endpoint: str, their_vk: str
    ) -> ConnectionInfo:
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post(
            "/connection",
            json=NewConnection(seed=seed, endpoint=endpoint, their_vk=their_vk).dict(),
        )

        if response.is_error:
            raise EchoClientError("Failed to create new connection")

        return ConnectionInfo.parse_obj(response.json())

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
        return response.json()

    async def receive_message(self, packed_message: bytes):
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        response = await self.client.post("/receive", content=packed_message)

        if response.is_error:
            raise EchoClientError("Failed to receive message")

    async def retrieve_messages(
        self, connection: Union[str, ConnectionInfo]
    ) -> List[Message]:
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        response = await self.client.get(f"/retrieve/{connection_id}")

        if response.is_error:
            raise EchoClientError("Failed to retrieve messages")

        return parse_obj_as(List[Message], response.json())

    async def wait_for_message(
        self,
        connection: Union[str, ConnectionInfo],
        thid: Optional[str] = None,
        msg_type: Optional[str] = None,
    ) -> Message:
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        response = await self.client.get(
            f"/wait-for/{connection_id}", params={"thid": thid, "msg_type": msg_type}
        )

        if response.is_error:
            raise EchoClientError("Failed to wait for message")

        return Message.parse_obj(response.json())

    async def send_message(
        self,
        connection: Union[str, ConnectionInfo],
        message: Union[Dict[str, Any], Message],
    ):
        if not self.client:
            raise NoOpenClient(
                "No client has been opened; use `async with echo_client`"
            )

        connection_id = (
            connection if isinstance(connection, str) else connection.connection_id
        )
        response = await self.client.post(f"/send/{connection_id}", json=message)

        if response.is_error:
            raise EchoClientError("Failed to send message")
