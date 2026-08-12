import struct
import tempfile
import unittest
from pathlib import Path

from ch1_melody_extractor import Note, extract_highest_notes, split_notes


def encode_vlq(value: int) -> bytes:
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(buffer))


def write_simple_midi(path: Path, events: list[tuple[int, bytes]]) -> None:
    track_data = bytearray()
    for delta, payload in events:
        track_data.extend(encode_vlq(delta))
        track_data.extend(payload)
    track_data.extend(b"\x00\xFF\x2F\x00")

    midi = bytearray()
    midi.extend(struct.pack(">4sIHHH", b"MThd", 6, 0, 1, 480))
    midi.extend(struct.pack(">4sI", b"MTrk", len(track_data)))
    midi.extend(track_data)
    path.write_bytes(bytes(midi))


def read_note_intervals(path: Path) -> list[tuple[int, int, int, int]]:
    data = path.read_bytes()
    track_length = struct.unpack(">I", data[18:22])[0]
    track = data[22 : 22 + track_length]
    offset = 0
    abs_time = 0
    running_status = None
    active: dict[tuple[int, int], list[int]] = {}
    notes: list[tuple[int, int, int, int]] = []

    while offset < len(track):
        delta = 0
        while True:
            byte = track[offset]
            offset += 1
            delta = (delta << 7) | (byte & 0x7F)
            if not byte & 0x80:
                break
        abs_time += delta

        status = track[offset]
        if status < 0x80:
            status = running_status
        else:
            offset += 1
            running_status = status if status < 0xF0 else None

        if status == 0xFF:
            meta_type = track[offset]
            offset += 1
            length = track[offset]
            offset += 1 + length
            if meta_type == 0x2F:
                break
            continue

        message_type = status & 0xF0
        channel = status & 0x0F
        data_length = 1 if message_type in (0xC0, 0xD0) else 2
        payload = track[offset : offset + data_length]
        offset += data_length

        is_note_on = message_type == 0x90 and payload[1] != 0
        is_note_off = message_type == 0x80 or (message_type == 0x90 and payload[1] == 0)

        if is_note_on:
            active.setdefault((channel, payload[0]), []).append(abs_time)
        elif is_note_off and active.get((channel, payload[0])):
            start = active[(channel, payload[0])].pop()
            notes.append((channel + 1, payload[0], start, abs_time))

    return sorted(notes)


class SplitNotesTests(unittest.TestCase):
    def test_highest_note_is_split_per_time_slice(self) -> None:
        notes = [
            Note(track_index=0, channel=0, pitch=60, velocity=80, off_velocity=0, start=0, end=480, sequence=0),
            Note(track_index=0, channel=0, pitch=64, velocity=80, off_velocity=0, start=0, end=480, sequence=1),
            Note(track_index=0, channel=0, pitch=67, velocity=80, off_velocity=0, start=240, end=480, sequence=2),
        ]

        song, harmony = split_notes(notes)

        self.assertEqual(
            [(segment.pitch, segment.start, segment.end) for segment in song],
            [(64, 0, 240), (67, 240, 480)],
        )
        self.assertEqual(
            [(segment.pitch, segment.start, segment.end) for segment in harmony],
            [(60, 0, 480), (64, 240, 480)],
        )


class ExtractionIntegrationTests(unittest.TestCase):
    def test_cli_logic_writes_song_and_harmony_mid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / "input.mid"

            write_simple_midi(
                input_path,
                [
                    (0, b"\xFF\x51\x03\x07\xA1\x20"),
                    (0, b"\x90\x3C\x50"),
                    (0, b"\x90\x40\x50"),
                    (0, b"\x91\x32\x45"),
                    (240, b"\x90\x43\x50"),
                    (240, b"\x80\x43\x00"),
                    (0, b"\x81\x32\x00"),
                    (0, b"\x80\x3C\x00"),
                    (0, b"\x80\x40\x00"),
                ],
            )

            extract_highest_notes(
                input_path=input_path,
                song_path=tmp_path / "Song.mid",
                harmony_path=tmp_path / "Harmony.mid",
                channel_number=1,
            )

            self.assertEqual(
                read_note_intervals(tmp_path / "Song.mid"),
                [(1, 64, 0, 240), (1, 67, 240, 480)],
            )
            self.assertEqual(
                read_note_intervals(tmp_path / "Harmony.mid"),
                [(1, 60, 0, 480), (1, 64, 240, 480), (2, 50, 0, 480)],
            )


if __name__ == "__main__":
    unittest.main()
