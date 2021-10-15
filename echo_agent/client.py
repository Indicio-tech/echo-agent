"""Client to Echo Agent."""
from contextlib import asynccontextmanager
from typing import List, Optional, Union
from aries_staticagent.message import Message
from httpx import AsyncClient
from pydantic.tools import parse_obj_as

from .models import ConnectionInfo, NewConnection

class EchoClientError(Exception):
    """General echo client error."""


class NoOpenClient(EchoClientError):
    """Raised when no client is open."""


class EchoClient:
    """Interact with a remote echo agent."""
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: Optional[AsyncClient] = None

    @asynccontextmanager
    async def __call__(self):
        async with AsyncClient(base_url=self.base_url) as client:
            self.client = client
            try:
                yield self
            finally:
                self.client = None

    async def new_connection(
        self, seed: Union[str, bytes], endpoint: str, their_vk: str
    ) -> ConnectionInfo:
        if not self.client:
            raise NoOpenClient("No client has been opened; use `async with echo_client`")

        response = await self.client.post(
            "/connection", json=NewConnection(
                seed=seed, endpoint=endpoint, their_vk=their_vk
            ).dict()
        )

        if not response.is_error:
            raise EchoClientError("Failed to create new connection")

        return ConnectionInfo.parse_obj(response.json())

    async def receive_message(self, packed_message: bytes):
        if not self.client:
            raise NoOpenClient("No client has been opened; use `async with echo_client`")

        response = await self.client.post(
            "/receive", content=packed_message
        )

        if response.is_error:
            raise EchoClientError("Failed to receive message")

    async def retrieve_messages(self, connection_id: str) -> List[Message]:
        if not self.client:
            raise NoOpenClient("No client has been opened; use `async with echo_client`")

        response = await self.client.get(f"/retrieve/{connection_id}")

        if response.is_error:
            raise EchoClientError("Failed to retrieve messages")
        
        return parse_obj_as(List[Message], response.json())

    async def wait_for_message(
        self, connection_id: str, thid: Optional[str] = None, msg_type: Optional[str] = None
    ) -> Message:
        if not self.client:
            raise NoOpenClient("No client has been opened; use `async with echo_client`")

        response = await self.client.get(f"/wait-for/{connection_id}", params={"thid": thid, "msg_type": msg_type})

        if response.is_error:
            raise EchoClientError("Failed to wait for message")

        return Message.parse_obj(response.json())

    async def send_message(self, connection_id: str, message: Message):
        if not self.client:
            raise NoOpenClient("No client has been opened; use `async with echo_client`")

        response = await self.client.post(f"/send/{connection_id}", json=message)

        if response.is_error:
            raise EchoClientError("Failed to send message")
