# engine.py
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
