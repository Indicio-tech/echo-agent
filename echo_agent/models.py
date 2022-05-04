from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class NewConnection:
    seed: str = field(metadata={"example": "00000000000000000000000000000000"})
    endpoint: str
    their_vk: str


@dataclass
class ConnectionInfo:
    connection_id: str
    did: str
    verkey: str
    their_vk: str
    endpoint: str


@dataclass
class SessionInfo:
    session_id: str
    connection_id: str


@dataclass
class Webhook:
    topic: str
    payload: Dict[str, Any]
