from pydantic import BaseModel, Field


class NewConnection(BaseModel):
    seed: str = Field(..., example="00000000000000000000000000000000")
    endpoint: str
    their_vk: str


class ConnectionInfo(BaseModel):
    connection_id: str
    did: str
    verkey: str
    their_vk: str
