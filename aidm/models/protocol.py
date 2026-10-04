"""Websocket protocol messages (single source of truth; see scripts/gen_protocol.py)."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class Ping(BaseModel):
    type: Literal["ping"]


class Pong(BaseModel):
    type: Literal["pong"]


ClientMsg = Annotated[Ping, Field(discriminator="type")]
ServerMsg = Annotated[Pong, Field(discriminator="type")]

CLIENT_MESSAGES: tuple[type[BaseModel], ...] = (Ping,)
SERVER_MESSAGES: tuple[type[BaseModel], ...] = (Pong,)

client_adapter: TypeAdapter[Ping] = TypeAdapter(ClientMsg)
server_adapter: TypeAdapter[Pong] = TypeAdapter(ServerMsg)
