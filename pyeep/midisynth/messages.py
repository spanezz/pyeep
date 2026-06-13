from typing import NamedTuple, Any, Annotated, override

import pydantic

from pyeep.models.messages import Message


class MIDIMessage(NamedTuple):
    """Raw received MIDI message."""

    #: JACK frame time
    frame_time: int
    #: Encoded MIDI message
    message: bytes

    @override
    def __str__(self) -> str:
        import mido

        msg = mido.Message.from_bytes(self.message)
        return f"MIDI(t={self.frame_time}, msg={msg})"


def serialize_midimessage(msg: MIDIMessage) -> dict[str, int | str]:
    return {"t": msg.frame_time, "m": msg.message.hex()}


def validate_midimessage(value: Any) -> MIDIMessage:
    match value:
        case MIDIMessage():
            return value
        case dict():
            return MIDIMessage(
                frame_time=int(value["t"]), message=bytes.fromhex(value["m"])
            )
        case _:
            raise ValueError("value must be a MIDIMessage or a dict")


type SerializableMIDIMessage = Annotated[
    MIDIMessage,
    pydantic.PlainSerializer(serialize_midimessage, return_type=dict),
    pydantic.BeforeValidator(validate_midimessage),
]


class MIDIMessages(Message):
    """Bundle of MIDI messages received together."""

    #: JACK frame time for this bundle of messages
    frame_time: int
    #: Message bundle
    messages: list[SerializableMIDIMessage]

    @pydantic.field_serializer("messages", mode="plain")
    def _serialize_messages(
        self, value: list[MIDIMessage]
    ) -> list[dict[str, int | str]]:
        return [{"t": msg.frame_time, "m": msg.message.hex()} for msg in value]
