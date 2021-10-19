import logging

from .models import ConnectionInfo, NewConnection


LOGGER = logging.getLogger(__name__)


try:
    from .app import app
    from aries_staticagent.message import Message
except ModuleNotFoundError:
    LOGGER.warning("Server dependencies not found; install extra `server` if needed")

try:
    from .client import EchoClient, EchoClientError, NoOpenClient
except ModuleNotFoundError:
    LOGGER.warning("Client dependencies not found; install extra `client` if needed")

__all__ = [
    "NewConnection",
    "ConnectionInfo",
    "Message",
    "EchoClient",
    "EchoClientError",
    "NoOpenClient",
    "app",
]
