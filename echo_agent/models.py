from dataclasses import dataclass, field
from typing import Any, Dict, Sequence


@dataclass
class NewConnection:
    seed: str = field(metadata={"example": "00000000000000000000000000000000"})
    endpoint: str
    recipient_keys: Sequence[str] = field(default_factory=list)
    routing_keys: Sequence[str] = field(default_factory=list)


@dataclass
class ConnectionInfo:
    connection_id: str
    did: str
    verkey: str
    endpoint: str
    recipient_keys: Sequence[str] = field(default_factory=list)
    routing_keys: Sequence[str] = field(default_factory=list)


@dataclass
class SessionInfo:
    session_id: str
    connection_id: str


@dataclass
class Webhook:
    topic: str
    payload: Dict[str, Any]
