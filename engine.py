# engine.py
# engine.py
from dataclasses import dataclass, field
from typing import List

import mido


# =====================================================
# NOTE EVENT
# =====================================================

@dataclass
class NoteEvent:

    tick: int
    note: int
    velocity: int
    channel: int
    on: bool


# =====================================================
# CHORD
# =====================================================

@dataclass
class ChordGroup:

    start_tick: int

    notes: List[NoteEvent] = field(default_factory=list)


# =====================================================
# Melody Extractor
# =====================================================

class MelodyExtractor:

    def __init__(self, tick_tolerance=10):

        self.tick_tolerance = tick_tolerance

        self.mid = None

        self.events = []

        self.groups = []

    # =====================================================
    # LOAD
    # =====================================================

    def load(self, filename):

        self.mid = mido.MidiFile(filename)

        self.events.clear()

        self.groups.clear()

        return self.mid

    # =====================================================
    # COLLECT EVENTS
    # =====================================================

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

                            on=(msg.velocity > 0)

                        )

                    )

                elif msg.type == "note_off":

                    self.events.append(

                        NoteEvent(

                            tick=abs_tick,

                            note=msg.note,

                            velocity=0,

                            channel=msg.channel,

                            on=False

                        )

                    )

        self.events.sort(

            key=lambda e: e.tick

        )

        # =====================================================
    # GROUP CHORDS
    # =====================================================

    def group_chords(self):

        self.groups.clear()

        current = None

        for event in self.events:

            # NOTE OFFは無視
            if not event.on:
                continue

            # 最初の和音
            if current is None:

                current = ChordGroup(
                    start_tick=event.tick
                )

                current.notes.append(event)

                self.groups.append(current)

                continue

            # 直前ノートとの差で判定
            last_tick = current.notes[-1].tick

            if (
                event.tick - last_tick
                <= self.tick_tolerance
            ):

                current.notes.append(event)

            else:

                current = ChordGroup(
                    start_tick=event.tick
                )

                current.notes.append(event)

                self.groups.append(current)

        return self.groups

    # =====================================================
    # ANALYZE
    # =====================================================

    def analyze(self):

        if not self.groups:

            self.group_chords()

        note_count = len(

            [e for e in self.events if e.on]

        )

        chord_count = len(self.groups)

        max_polyphony = max(

            (len(c.notes) for c in self.groups),

            default=0

        )

        average_polyphony = (

            sum(

                len(c.notes)

                for c in self.groups

            )

            / chord_count

            if chord_count else 0

        )

        return {

            "note_count": note_count,

            "chord_count": chord_count,

            "max_polyphony": max_polyphony,

            "average_polyphony":

                round(

                    average_polyphony,

                    2

                )

        }

    # =====================================================
    # SONG (Highest)
    # =====================================================

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

    # =====================================================
    # HARMONY
    # =====================================================

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

    # =====================================================
    # DEBUG
    # =====================================================

    def print_groups(self):

        for i, group in enumerate(self.groups):

            print(f"Chord {i+1}")

            for note in group.notes:

                print(

                    f" Tick={note.tick}"

                    f" Note={note.note}"

                    f" Vel={note.velocity}"

                )

    # =====================================================
    # BUILD NOTE PAIRS
    # =====================================================

    def build_note_pairs(self, note_list):

        pairs = []
        used_off = set()

        for note in note_list:

            note_off = None

            # for event in self.events:
            for i, event in enumerate(self.events):

                if i in used_off:
                    continue

                if (
                    not event.on
                    and event.note == note.note
                    and event.channel == note.channel
                    and event.tick >= note.tick
                ):

                    note_off = event
                    used_off.add(i)
                    break

            if note_off is None:
                continue

            pairs.append(
                {
                    "on": note,
                    "off": note_off
                }
            )

        return pairs

    # =====================================================
    # SAVE MIDI
    # =====================================================

    def save_midi(self, note_pairs, filename):

        new_mid = mido.MidiFile(
            ticks_per_beat=self.mid.ticks_per_beat
        )

        # -----------------------------------------
        # Track0 : Tempo / Signature
        # -----------------------------------------

        meta_track = mido.MidiTrack()

        new_mid.tracks.append(meta_track)

        abs_tick = 0
        last_tick = 0

        if len(self.mid.tracks) > 0:

            for msg in self.mid.tracks[0]:

                abs_tick += msg.time

                if (
                    msg.is_meta
                    and msg.type in (
                        "set_tempo",
                        "time_signature",
                        "key_signature"
                    )
                ):

                    copy_msg = msg.copy()

                    copy_msg.time = (
                        abs_tick - last_tick
                    )

                    last_tick = abs_tick

                    meta_track.append(copy_msg)

        meta_track.append(

            mido.MetaMessage(

                "end_of_track",

                time=0

            )

        )

        # -----------------------------------------
        # Track1 : Notes
        # -----------------------------------------

        note_track = mido.MidiTrack()

        new_mid.tracks.append(note_track)

        # Program Changeコピー

        for src_track in self.mid.tracks:

            abs_tick = 0

            found = False

            for msg in src_track:

                abs_tick += msg.time

                if msg.type == "program_change":

                    note_track.append(

                        mido.Message(

                            "program_change",

                            channel=msg.channel,

                            program=msg.program,

                            time=0

                        )

                    )

                    found = True

                    break

            if found:

                break

        # -----------------------------------------
        # NOTEイベント生成
        # -----------------------------------------

        events = []

        for pair in note_pairs:

            on = pair["on"]

            off = pair["off"]

            events.append(

                (

                    on.tick,

                    1,

                    on.note,

                    on.velocity,

                    on.channel

                )

            )

            events.append(

                (

                    off.tick,

                    0,

                    off.note,

                    0,

                    off.channel

                )

            )

        # Tick順
        # 同TickではNOTE OFFを先

        events.sort(

            key=lambda e: (

                e[0],

                e[1]

            )

        )

        last_tick = 0

        for tick, flag, note, vel, ch in events:

            delta = tick - last_tick

            last_tick = tick

            if flag:

                note_track.append(

                    mido.Message(

                        "note_on",

                        note=note,

                        velocity=vel,

                        channel=ch,

                        time=delta

                    )

                )

            else:

                note_track.append(

                    mido.Message(

                        "note_off",

                        note=note,

                        velocity=0,

                        channel=ch,

                        time=delta

                    )

                )

        note_track.append(

            mido.MetaMessage(

                "end_of_track",

                time=0

            )

        )

        new_mid.save(str(filename))

    # =====================================================
    # SAVE SONG
    # =====================================================

    def save_song(self, filename):

        if not self.groups:
            self.group_chords()

        song_notes = self.extract_song()

        pairs = self.build_note_pairs(song_notes)

        self.save_midi(
            pairs,
            filename
        )

    # =====================================================
    # SAVE HARMONY
    # =====================================================

    def save_harmony(self, filename):

        if not self.groups:
            self.group_chords()

        harmony_notes = self.extract_harmony()

        pairs = self.build_note_pairs(harmony_notes)

        self.save_midi(
            pairs,
            filename
        )


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    engine = MelodyExtractor(10)

    print("Engine Test")

    # ここは必要に応じて変更
    midi = "sample.mid"

    try:

        engine.load(midi)

        engine.collect_events()

        engine.group_chords()

        info = engine.analyze()

        print(info)

    except Exception as e:

        print(e)
