import json

from pyeep.midisynth.messages import MIDIMessage, MIDIMessages
from pyeep.test.messages import EventTestCase


class TestMIDIMessages(EventTestCase):
    message_cls = MIDIMessages
    samples = {
        "empty": MIDIMessages(frame_time=0, messages=[]),
        "one": MIDIMessages(frame_time=1, messages=[MIDIMessage(42, b"123")]),
        "many": MIDIMessages(
            frame_time=2,
            messages=[
                MIDIMessage(1, b"1"),
                MIDIMessage(2, b"2"),
                MIDIMessage(3, b"3"),
            ],
        ),
    }

    def test_serialize_messages(self) -> None:
        msg = self.samples["many"]
        self.assertEqual(
            json.loads(msg.as_json)["messages"],
            [
                {"t": 1, "m": "31"},
                {"t": 2, "m": "32"},
                {"t": 3, "m": "33"},
            ],
        )

    def test_members(self) -> None:
        self.assertEqual(self.samples["empty"].frame_time, 0)
        self.assertEqual(self.samples["empty"].messages, [])
        self.assertEqual(self.samples["one"].frame_time, 1)
        self.assertEqual(
            self.samples["one"].messages, [MIDIMessage(42, b"123")]
        )
        self.assertEqual(self.samples["many"].frame_time, 2)
        self.assertEqual(
            self.samples["many"].messages,
            [
                MIDIMessage(1, b"1"),
                MIDIMessage(2, b"2"),
                MIDIMessage(3, b"3"),
            ],
        )
