from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence


@dataclass
class NewConnection:
    seed: str = field(metadata={"example": "00000000000000000000000000000000"})
    endpoint: str
    their_vk: Optional[str] = None
    recipient_keys: Optional[Sequence[str]] = None
    routing_keys: Optional[Sequence[str]] = None


@dataclass
class ConnectionInfo:
    connection_id: str
    did: str
    verkey: str
    their_vk: str
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
