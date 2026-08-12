from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class RawEvent:
    abs_time: int
    sequence: int
    raw: bytes


@dataclass(frozen=True)
class Note:
    track_index: int
    channel: int
    pitch: int
    velocity: int
    off_velocity: int
    start: int
    end: int
    sequence: int


@dataclass(frozen=True)
class NoteSegment:
    track_index: int
    channel: int
    pitch: int
    velocity: int
    off_velocity: int
    start: int
    end: int
    sequence: int


@dataclass(frozen=True)
class MidiTrackData:
    copied_events: Tuple[RawEvent, ...]
    harmony_only_events: Tuple[RawEvent, ...]
    end_of_track_time: int


@dataclass(frozen=True)
class MidiFileData:
    format_type: int
    division: int
    tracks: Tuple[MidiTrackData, ...]
    notes: Tuple[Note, ...]


def encode_vlq(value: int) -> bytes:
    if value < 0:
        raise ValueError("VLQ value must not be negative")
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append(0x80 | (value & 0x7F))
        value >>= 7
    return bytes(reversed(buffer))


def decode_vlq(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset


def parse_track(track_index: int, data: bytes, target_channel: int) -> Tuple[MidiTrackData, List[Note]]:
    offset = 0
    abs_time = 0
    sequence = 0
    copied_events: List[RawEvent] = []
    harmony_only_events: List[RawEvent] = []
    notes: List[Note] = []
    active_notes: Dict[Tuple[int, int], List[Tuple[int, int, int, int]]] = {}
    running_status: int | None = None
    end_of_track_time = 0

    while offset < len(data):
        delta, offset = decode_vlq(data, offset)
        abs_time += delta
        status = data[offset]

        if status < 0x80:
            if running_status is None:
                raise ValueError("Running status encountered before status byte")
            status = running_status
        else:
            offset += 1
            if status < 0xF0:
                running_status = status
            else:
                running_status = None

        if status == 0xFF:
            meta_type = data[offset]
            offset += 1
            length, offset = decode_vlq(data, offset)
            payload = data[offset : offset + length]
            offset += length
            raw = bytes([0xFF, meta_type]) + encode_vlq(length) + payload
            if meta_type == 0x2F:
                end_of_track_time = abs_time
            else:
                copied_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
                harmony_only_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
        elif status in (0xF0, 0xF7):
            length, offset = decode_vlq(data, offset)
            payload = data[offset : offset + length]
            offset += length
            raw = bytes([status]) + encode_vlq(length) + payload
            copied_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
            harmony_only_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
        else:
            message_type = status & 0xF0
            channel = status & 0x0F
            data_length = 1 if message_type in (0xC0, 0xD0) else 2
            message_data = data[offset : offset + data_length]
            offset += data_length
            raw = bytes([status]) + message_data

            is_note_on = message_type == 0x90 and len(message_data) == 2 and message_data[1] != 0
            is_note_off = message_type == 0x80 or (
                message_type == 0x90 and len(message_data) == 2 and message_data[1] == 0
            )

            if not (is_note_on or is_note_off):
                copied_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
                harmony_only_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
            elif channel != target_channel:
                harmony_only_events.append(RawEvent(abs_time=abs_time, sequence=sequence, raw=raw))
            elif is_note_on:
                key = (channel, message_data[0])
                active_notes.setdefault(key, []).append(
                    (abs_time, message_data[1], sequence, track_index)
                )
            else:
                key = (channel, message_data[0])
                starts = active_notes.get(key)
                if starts:
                    start_time, velocity, start_sequence, start_track = starts.pop()
                    notes.append(
                        Note(
                            track_index=start_track,
                            channel=channel,
                            pitch=message_data[0],
                            velocity=velocity,
                            off_velocity=message_data[1],
                            start=start_time,
                            end=abs_time,
                            sequence=start_sequence,
                        )
                    )
                    if not starts:
                        active_notes.pop(key, None)
            sequence += 1
            continue

        sequence += 1

    if end_of_track_time == 0:
        end_of_track_time = abs_time

    for (channel, pitch), starts in active_notes.items():
        for start_time, velocity, start_sequence, start_track in starts:
            notes.append(
                Note(
                    track_index=start_track,
                    channel=channel,
                    pitch=pitch,
                    velocity=velocity,
                    off_velocity=0,
                    start=start_time,
                    end=end_of_track_time,
                    sequence=start_sequence,
                )
            )

    return (
        MidiTrackData(
            copied_events=tuple(copied_events),
            harmony_only_events=tuple(harmony_only_events),
            end_of_track_time=end_of_track_time,
        ),
        notes,
    )


def read_midi(path: Path, target_channel: int) -> MidiFileData:
    data = path.read_bytes()
    if data[:4] != b"MThd":
        raise ValueError("Unsupported MIDI file: missing MThd header")

    header_length = struct.unpack(">I", data[4:8])[0]
    if header_length != 6:
        raise ValueError("Unsupported MIDI header length")

    format_type, track_count, division = struct.unpack(">HHH", data[8:14])
    offset = 8 + header_length
    tracks: List[MidiTrackData] = []
    notes: List[Note] = []

    for track_index in range(track_count):
        if data[offset : offset + 4] != b"MTrk":
            raise ValueError(f"Unsupported MIDI file: missing MTrk chunk for track {track_index}")
        track_length = struct.unpack(">I", data[offset + 4 : offset + 8])[0]
        track_data = data[offset + 8 : offset + 8 + track_length]
        offset += 8 + track_length
        track, track_notes = parse_track(track_index, track_data, target_channel)
        tracks.append(track)
        notes.extend(track_notes)

    return MidiFileData(
        format_type=format_type,
        division=division,
        tracks=tuple(tracks),
        notes=tuple(sorted(notes, key=lambda note: (note.start, note.sequence, note.pitch))),
    )


def split_notes(notes: Sequence[Note]) -> Tuple[List[NoteSegment], List[NoteSegment]]:
    if not notes:
        return [], []

    note_ids = list(range(len(notes)))
    starts: Dict[int, List[int]] = {}
    ends: Dict[int, List[int]] = {}
    times = set()

    for note_id, note in enumerate(notes):
        starts.setdefault(note.start, []).append(note_id)
        ends.setdefault(note.end, []).append(note_id)
        times.add(note.start)
        times.add(note.end)

    sorted_times = sorted(times)
    active: set[int] = set()
    clip_states: Dict[Tuple[str, int], NoteSegment] = {}
    song_segments: List[NoteSegment] = []
    harmony_segments: List[NoteSegment] = []

    for index, current_time in enumerate(sorted_times[:-1]):
        for note_id in ends.get(current_time, []):
            active.discard(note_id)
        for note_id in starts.get(current_time, []):
            active.add(note_id)

        next_time = sorted_times[index + 1]
        if next_time <= current_time or not active:
            continue

        highest_pitch = max(notes[note_id].pitch for note_id in active)
        active_ids = sorted(active, key=lambda note_id: (notes[note_id].sequence, notes[note_id].pitch))

        for note_id in active_ids:
            note = notes[note_id]
            destination = "song" if note.pitch == highest_pitch else "harmony"
            key = (destination, note_id)
            existing = clip_states.get(key)

            if existing and existing.end == current_time:
                updated = NoteSegment(
                    track_index=existing.track_index,
                    channel=existing.channel,
                    pitch=existing.pitch,
                    velocity=existing.velocity,
                    off_velocity=existing.off_velocity,
                    start=existing.start,
                    end=next_time,
                    sequence=existing.sequence,
                )
                clip_states[key] = updated
                if destination == "song":
                    song_segments[-1] = updated
                else:
                    harmony_segments[-1] = updated
            else:
                segment = NoteSegment(
                    track_index=note.track_index,
                    channel=note.channel,
                    pitch=note.pitch,
                    velocity=note.velocity,
                    off_velocity=note.off_velocity,
                    start=current_time,
                    end=next_time,
                    sequence=note.sequence,
                )
                clip_states[key] = segment
                if destination == "song":
                    song_segments.append(segment)
                else:
                    harmony_segments.append(segment)

    return song_segments, harmony_segments


def encode_note_on(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x90 | channel, pitch, velocity])


def encode_note_off(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x80 | channel, pitch, velocity])


def build_track_bytes(
    track: MidiTrackData,
    segments: Iterable[NoteSegment],
    include_harmony_only_events: bool,
) -> bytes:
    sortable_events: List[Tuple[int, int, int, bytes]] = []

    for event in track.copied_events:
        sortable_events.append((event.abs_time, 20, event.sequence, event.raw))
    if include_harmony_only_events:
        for event in track.harmony_only_events:
            sortable_events.append((event.abs_time, 20, event.sequence, event.raw))

    for segment in segments:
        sortable_events.append(
            (segment.start, 30, segment.sequence, encode_note_on(segment.channel, segment.pitch, segment.velocity))
        )
        sortable_events.append(
            (segment.end, 10, segment.sequence, encode_note_off(segment.channel, segment.pitch, segment.off_velocity))
        )

    final_time = max(
        [track.end_of_track_time]
        + [event_time for event_time, _, _, _ in sortable_events],
        default=track.end_of_track_time,
    )
    sortable_events.append((final_time, 99, 0, b"\xFF\x2F\x00"))
    sortable_events.sort()

    buffer = bytearray()
    previous_time = 0
    for abs_time, _, _, raw in sortable_events:
        buffer.extend(encode_vlq(abs_time - previous_time))
        buffer.extend(raw)
        previous_time = abs_time
    return bytes(buffer)


def write_midi(
    path: Path,
    midi_data: MidiFileData,
    track_segments: Dict[int, List[NoteSegment]],
    include_harmony_only_events: bool,
) -> None:
    header = struct.pack(
        ">4sIHHH",
        b"MThd",
        6,
        midi_data.format_type,
        len(midi_data.tracks),
        midi_data.division,
    )

    chunks = [header]
    for track_index, track in enumerate(midi_data.tracks):
        data = build_track_bytes(
            track=track,
            segments=track_segments.get(track_index, []),
            include_harmony_only_events=include_harmony_only_events,
        )
        chunks.append(struct.pack(">4sI", b"MTrk", len(data)))
        chunks.append(data)

    path.write_bytes(b"".join(chunks))


def group_segments_by_track(segments: Sequence[NoteSegment]) -> Dict[int, List[NoteSegment]]:
    grouped: Dict[int, List[NoteSegment]] = {}
    for segment in segments:
        grouped.setdefault(segment.track_index, []).append(segment)
    return grouped


def extract_highest_notes(
    input_path: Path,
    song_path: Path,
    harmony_path: Path,
    channel_number: int = 1,
) -> None:
    if not 1 <= channel_number <= 16:
        raise ValueError("Channel must be between 1 and 16")

    midi_data = read_midi(input_path, target_channel=channel_number - 1)
    song_segments, harmony_segments = split_notes(midi_data.notes)

    write_midi(
        path=song_path,
        midi_data=midi_data,
        track_segments=group_segments_by_track(song_segments),
        include_harmony_only_events=False,
    )
    write_midi(
        path=harmony_path,
        midi_data=midi_data,
        track_segments=group_segments_by_track(harmony_segments),
        include_harmony_only_events=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a Studio One CH1 MIDI into Song.mid (highest note) and Harmony.mid (remaining notes)."
    )
    parser.add_argument("input", type=Path, help="Path to the source MIDI file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory where Song.mid and Harmony.mid will be written (defaults to the input file directory)",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=1,
        help="1-based MIDI channel number to extract (default: 1)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path: Path = args.input.resolve()
    output_dir: Path = (args.output_dir or input_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    extract_highest_notes(
        input_path=input_path,
        song_path=output_dir / "Song.mid",
        harmony_path=output_dir / "Harmony.mid",
        channel_number=args.channel,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
