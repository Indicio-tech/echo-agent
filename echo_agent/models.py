from pydantic import BaseModel, Field
from typing import List, Literal, Union


class NewConnection(BaseModel):
    seed: str = Field(..., metadata={"example": "00000000000000000000000000000000"})
    endpoint: str
    their_vk: str


class ConnectionInvitation(BaseModel):
    type: Union[
        Literal["did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/connections/1.0/invitation"],
        Literal["https://didcomm.org/connections/1.0/invitation"],
    ] = Field(..., alias="@type")
    id: str = Field(..., alias="@id")
    recipient_keys: List[str] = Field(..., alias="recipientKeys")
    routing_keys: List[str] = Field(..., alias="routingKeys")
    service_endpoint: str = Field(..., alias="serviceEndpoint")
    label: str


class Service(BaseModel):
    id: str
    type: Literal["did-communication"]
    recipient_keys: List[str] = Field(..., alias="recipientKeys")
    routing_keys: List[str] = Field(..., alias="routingKeys")
    service_endpoint: str = Field(..., alias="serviceEndpoint")


class OutOfBandInvitation(BaseModel):
    type: Union[
        Literal["did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/out-of-band/1.0/invitation"],
        Literal["https://didcomm.org/out-of-band/1.0/invitation"],
        Literal["did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/out-of-band/1.1/invitation"],
        Literal["https://didcomm.org/out-of-band/1.1/invitation"],
    ] = Field(..., alias="@type")
    id: str = Field(..., alias="@id")
    label: str
    handshake_protocols: List[
        Union[
            Literal["https://didcomm.org/didexchange/1.0"],
            Literal["https://didcomm.org/connections/1.0"],
        ]
    ]
    services: List[Service]


class ConnectionInfo(BaseModel):
    connection_id: str
    did: str
    verkey: str
    their_vk: str
    endpoint: str


class SessionInfo(BaseModel):
    session_id: str
    connection_id: str
