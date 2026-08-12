# engine.py
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
import mido


@dataclass
class NoteEvent:
    tick: int
    note: int
    velocity: int
    channel: int
    on: bool


@dataclass
class ChordGroup:
    start_tick: int
    notes: List[NoteEvent] = field(default_factory=list)


class MelodyExtractor:

    def __init__(self, tick_tolerance=10):
        self.tick_tolerance = tick_tolerance
        self.mid = None
        self.events = []
        self.groups = []

    # ----------------------------
    # MIDI読込
    # ----------------------------
    def load(self, filename):

        self.mid = mido.MidiFile(filename)

        self.events.clear()
        self.groups.clear()

        return self.mid

    # ----------------------------
    # NOTEイベント取得
    # ----------------------------
    def collect_events(self):

        self.events.clear()

        for track in self.mid.tracks:

            abs_tick = 0

            for msg in track:

                abs_tick += msg.time

                if msg.type == "note_on":

                    self.events.append(
                        NoteEvent(
                            tick=abs_tick,
                            note=msg.note,
                            velocity=msg.velocity,
                            channel=msg.channel,
                            on=(msg.velocity > 0),
                        )
                    )

                elif msg.type == "note_off":

                    self.events.append(
                        NoteEvent(
                            tick=abs_tick,
                            note=msg.note,
                            velocity=0,
                            channel=msg.channel,
                            on=False,
                        )
                    )

        self.events.sort(key=lambda e: e.tick)

    # ----------------------------
    # 和音グループ作成
    # ----------------------------
    def group_chords(self):

        self.groups.clear()

        current = None

        for e in self.events:

            # NOTE OFFは無視
            if not e.on:
                continue

            if current is None:

                current = ChordGroup(start_tick=e.tick)
                current.notes.append(e)
                self.groups.append(current)

                continue

            if e.tick - current.start_tick <= self.tick_tolerance:

                current.notes.append(e)

            else:

                current = ChordGroup(start_tick=e.tick)
                current.notes.append(e)
                self.groups.append(current)

        return self.groups

    # ----------------------------
    # デバッグ表示
    # ----------------------------
    def print_groups(self):

        for i, g in enumerate(self.groups):

            print(f"Chord {i+1}")

            for n in g.notes:

                print(
                    f"  Tick={n.tick} "
                    f"Note={n.note} "
                    f"Velocity={n.velocity}"
                )

    # ----------------------------
    # 解析情報
    # ----------------------------
    def analyze(self):

        if not self.groups:
            self.group_chords()

        note_count = len([e for e in self.events if e.on])

        chord_count = len(self.groups)

        max_polyphony = max(
            (len(ch.notes) for ch in self.groups),
            default=0
        )

        average_polyphony = (
            sum(len(ch.notes) for ch in self.groups) / chord_count
            if chord_count else 0
        )

        return {
            "note_count": note_count,
            "chord_count": chord_count,
            "max_polyphony": max_polyphony,
            "average_polyphony": round(average_polyphony, 2)
        }

    # ----------------------------
    # Song（最高音）
    # ----------------------------

    def extract_song(self):

        song = []

        for chord in self.groups:

            if not chord.notes:
                continue

            highest = max(
                chord.notes,
                key=lambda n: n.note
            )

            song.append(highest)

        return song

    # ----------------------------
    # Harmony（残り）
    # ----------------------------

    def extract_harmony(self):

        harmony = []

        for chord in self.groups:

            if len(chord.notes) <= 1:
                continue

            highest = max(
                chord.notes,
                key=lambda n: n.note
            )

            for note in chord.notes:

                if note is highest:
                    continue

                harmony.append(note)

        return harmony

    # ----------------------------
    # Song/Harmonyイベント生成
    # ----------------------------
    def build_track(self, note_list):

        track = []

        for note in note_list:

            track.append(
                {
                    "tick": note.tick,
                    "note": note.note,
                    "velocity": note.velocity,
                    "channel": note.channel
                }
            )

        track.sort(key=lambda x: x["tick"])

        return track

    # ----------------------------
    # Song/Harmony取得
    # ----------------------------

    def split(self):

        song = self.build_track(
            self.extract_song()
        )

        harmony = self.build_track(
            self.extract_harmony()
        )

        return song, harmony

    # ----------------------------
    # NOTE ON/OFF ペア作成
    # ----------------------------
    def build_note_pairs(self, note_list):

        pairs = []

        for note in note_list:

            note_off = None

            for e in self.events:

                if (
                    not e.on
                    and e.note == note.note
                    and e.tick >= note.tick
                ):
                    note_off = e
                    break

            if note_off is None:
                continue

            pairs.append({
                "on": note,
                "off": note_off
            })

        return pairs
