"""Procedural chiptune audio: Pokemon cries, sound effects, and music all
synthesized at runtime with numpy -> pygame.mixer.Sound. No audio assets
are required, so every one of the 649 species gets a (unique-ish) cry for
free, the same way the renderer falls back to procedural sprite "blobs".

Three layers, in priority order, decide what actually plays for music:
  1. An external file in ``<game>/audio/music/<name>.{ogg,mp3,wav,mid}``
     (MIDI only if ``midi`` is enabled), played via pygame.mixer.music.
  2. Otherwise the built-in chiptune song, synthesized and looped.
MIDI is supported for authors who want to drop in their own tracks, but
SDL/pygame MIDI playback is environment-dependent (it needs a soft-synth /
soundfont) and silent failure can't be detected, so the synth is the
guaranteed-audible default. ``export_songs_to_midi`` writes the built-in
songs out as editable .mid files to bootstrap that workflow.

The mixer is initialized defensively: with no audio device (headless / CI /
no soundcard) the manager degrades to a safe no-op and the game runs
silently, never raising.
"""
from __future__ import annotations

import math
import os
import struct

import numpy as np

try:
    import pygame
except Exception:                       # pragma: no cover - pygame always present
    pygame = None

# Synthesis sample rate + output channel count; both are corrected to match
# the real mixer when the manager initializes.
RATE = 44100
CHANNELS = 2


# ── note / frequency math ────────────────────────────────────────────
_BASE = {"c": 0, "c#": 1, "db": 1, "d": 2, "d#": 3, "eb": 3, "e": 4, "f": 5,
         "f#": 6, "gb": 6, "g": 7, "g#": 8, "ab": 8, "a": 9, "a#": 10,
         "bb": 10, "b": 11}


def note_midi(name: str) -> int:
    """'C4' -> 60, 'A4' -> 69, 'F#3' -> 54."""
    s = name.strip().lower()
    i = 2 if len(s) > 1 and s[1] in "#b" else 1
    return (int(s[i:]) + 1) * 12 + _BASE[s[:i]]


def _freq(tok) -> float:
    """Frequency for a token that is a MIDI int, a note name, or a rest."""
    if tok is None or tok == 0 or tok == "r":
        return 0.0
    n = tok if isinstance(tok, int) else note_midi(tok)
    return 440.0 * 2.0 ** ((n - 69) / 12.0)


# ── oscillators (vectorized, float -1..1) ────────────────────────────
def _n(dur):
    return max(1, int(RATE * dur))


def square(freq, dur, duty=0.5):
    if freq <= 0:
        return np.zeros(_n(dur))
    t = np.arange(_n(dur)) / RATE
    return np.where((t * freq) % 1.0 < duty, 1.0, -1.0)


def triangle(freq, dur):
    if freq <= 0:
        return np.zeros(_n(dur))
    t = np.arange(_n(dur)) / RATE
    return 4.0 * np.abs(((t * freq) % 1.0) - 0.5) - 1.0


def saw(freq, dur):
    if freq <= 0:
        return np.zeros(_n(dur))
    t = np.arange(_n(dur)) / RATE
    return 2.0 * ((t * freq) % 1.0) - 1.0


def sine(freq, dur):
    if freq <= 0:
        return np.zeros(_n(dur))
    t = np.arange(_n(dur)) / RATE
    return np.sin(2 * np.pi * freq * t)


def noise(dur, rng):
    return rng.uniform(-1.0, 1.0, _n(dur))


def envelope(n, attack=0.005, release=0.04, sustain=1.0):
    env = np.full(n, float(sustain))
    a, r = min(int(RATE * attack), n // 2), min(int(RATE * release), n // 2)
    if a > 0:
        env[:a] = np.linspace(0.0, sustain, a)
    if r > 0:
        env[-r:] = np.linspace(sustain, 0.0, r)
    return env


def _to_sound(mono, volume=1.0):
    data = (np.clip(mono * volume, -1.0, 1.0) * 32767).astype(np.int16)
    if CHANNELS == 2:
        data = np.column_stack([data, data])
    return pygame.sndarray.make_sound(np.ascontiguousarray(data))


# ── cries: one per species, seeded by dex number ─────────────────────
def cry_buffer(seed: int):
    rng = np.random.RandomState(int(seed) & 0x7FFFFFFF)
    dur = rng.uniform(0.36, 0.60)
    n = _n(dur)
    t = np.linspace(0.0, 1.0, n)
    base = rng.uniform(160.0, 540.0)
    knots = rng.randint(3, 6)
    contour = base * np.interp(t, np.linspace(0, 1, knots),
                               rng.uniform(0.62, 1.85, knots))
    vib = 1.0 + rng.uniform(0.0, 0.05) * np.sin(2 * np.pi *
                                                rng.uniform(7, 19) * t)
    freq = contour * vib
    phase = np.cumsum(2 * np.pi * freq / RATE)
    timbre = rng.choice(["square", "pulse", "tri", "saw"])
    if timbre == "square":
        wave = np.sign(np.sin(phase))
    elif timbre == "pulse":
        wave = np.where((phase / (2 * np.pi)) % 1.0 < rng.uniform(0.2, 0.4),
                        1.0, -1.0)
    elif timbre == "tri":
        wave = (2.0 / np.pi) * np.arcsin(np.clip(np.sin(phase), -1, 1))
    else:
        wave = 2.0 * ((phase / (2 * np.pi)) % 1.0) - 1.0
    wave = 0.85 * wave + 0.15 * rng.uniform(-1, 1, n)        # a little breath
    amp = np.interp(t, [0, 0.15, 0.8, 1.0], [0.25, 1.0, 0.85, 0.0])
    return wave * envelope(n, attack=0.008,
                           release=float(rng.uniform(0.05, 0.14))) * amp


# ── sound effects ────────────────────────────────────────────────────
def _slide(f0, f1, dur, kind="square", duty=0.5):
    n = _n(dur)
    t = np.linspace(0, 1, n)
    freq = f0 * (f1 / f0) ** t
    phase = np.cumsum(2 * np.pi * freq / RATE)
    if kind == "square":
        w = np.where((phase / (2 * np.pi)) % 1.0 < duty, 1.0, -1.0)
    elif kind == "tri":
        w = (2 / np.pi) * np.arcsin(np.clip(np.sin(phase), -1, 1))
    else:
        w = np.sin(phase)
    return w * envelope(n, release=0.03)


def _seq(tokens, dur, kind="square", duty=0.5):
    return np.concatenate([square(_freq(tk), dur, duty) * envelope(_n(dur))
                           if kind == "square" else
                           triangle(_freq(tk), dur) * envelope(_n(dur))
                           for tk in tokens])


def _sfx(name, rng):
    if name == "menu_move":
        return square(_freq("a5"), 0.035, 0.5) * envelope(_n(0.035))
    if name == "menu_select":
        return _seq(["e5", "a5"], 0.05)
    if name == "menu_back":
        return _seq(["a5", "e5"], 0.05)
    if name == "confirm":
        return _seq(["c5", "g5"], 0.06)
    if name == "hit":
        return 0.6 * noise(0.07, rng) * envelope(_n(0.07), release=0.05) \
            + 0.4 * square(_freq("c4"), 0.07) * envelope(_n(0.07))
    if name == "hit_super":           # brighter, snappier
        return 0.6 * noise(0.09, rng) * envelope(_n(0.09), release=0.06) \
            + 0.4 * _slide(_freq("g4"), _freq("g5"), 0.09)
    if name == "hit_weak":            # duller thud
        return 0.5 * noise(0.06, rng) * envelope(_n(0.06)) \
            + 0.5 * triangle(_freq("g3"), 0.06) * envelope(_n(0.06))
    if name == "faint":
        return _slide(_freq("c5"), _freq("c3"), 0.5, "tri")
    if name == "ball_throw":
        return _slide(_freq("c4"), _freq("c6"), 0.18) * 0.6 \
            + 0.4 * noise(0.18, rng) * envelope(_n(0.18), release=0.12)
    if name == "ball_shake":
        return _seq(["a5", "r", "a5"], 0.03)
    if name == "ball_click":
        return _seq(["e5", "a5", "c6"], 0.06)
    if name == "ball_break":
        return _slide(_freq("c5"), _freq("e3"), 0.22, "square", 0.3)
    if name == "heal":
        return _seq(["c5", "e5", "g5", "c6"], 0.09, "tri")
    if name == "level_up":
        return _seq(["c5", "e5", "g5", "c6", "e6"], 0.08)
    if name == "low_hp":
        return _seq(["b5", "r", "b5"], 0.10)
    if name == "run":
        return _slide(_freq("a4"), _freq("a3"), 0.16, "square", 0.25)
    if name == "save":
        return _seq(["c5", "g5", "c6"], 0.10, "tri")
    if name == "bump":
        return triangle(_freq("c3"), 0.06) * envelope(_n(0.06))
    return np.zeros(_n(0.05))


SFX_NAMES = ("menu_move", "menu_select", "menu_back", "confirm", "hit",
             "hit_super", "hit_weak", "faint", "ball_throw", "ball_shake",
             "ball_click", "ball_break", "heal", "level_up", "low_hp",
             "run", "save", "bump")


# ── music: chord/pattern helpers keep songs tiny to author ───────────
_QUAL = {"maj": [0, 4, 7], "min": [0, 3, 7], "maj7": [0, 4, 7, 11],
         "min7": [0, 3, 7, 10], "dom7": [0, 4, 7, 10], "sus4": [0, 5, 7]}


def _chord(root, qual, octave):
    base = note_midi(f"{root}{octave}")
    return [base + iv for iv in _QUAL[qual]]


def arp(prog, pattern, octave, beats):
    """Arpeggiate a chord progression. `pattern` indexes chord tones;
    values past the chord length wrap up an octave."""
    out = []
    for root, qual in prog:
        tones = _chord(root, qual, octave)
        for p in pattern:
            out.append((tones[p % len(tones)] + 12 * (p // len(tones)), beats))
    return out


def bass(prog, octave, beats, per_chord=4):
    out = []
    for root, _ in prog:
        out += [(note_midi(f"{root}{octave}"), beats)] * per_chord
    return out


def drums(pattern, beats):
    return [(tok, beats) for tok in pattern]


# Original (non-copyrighted) chiptune loops. Roots spell simple progressions.
_TITLE = [("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")]
_BATTLE = [("A", "min"), ("F", "maj"), ("G", "maj"), ("E", "min")]
_TOWN = [("C", "maj"), ("F", "maj"), ("G", "maj"), ("C", "maj")]
_ROUTE = [("G", "maj"), ("C", "maj"), ("D", "maj"), ("G", "maj")]

SONGS = {
    "title": {"bpm": 96, "loop": True, "tracks": [
        {"inst": "pulse50", "vol": 0.45, "pan": 0.5,
         "notes": arp(_TITLE, [0, 2, 1, 2], 5, 0.5)},
        {"inst": "tri", "vol": 0.55, "pan": 0.5,
         "notes": bass(_TITLE, 3, 1.0, 2)}]},
    "town": {"bpm": 104, "loop": True, "tracks": [
        {"inst": "tri", "vol": 0.5, "pan": 0.45,
         "notes": arp(_TOWN, [0, 1, 2, 1], 5, 0.5)},
        {"inst": "tri", "vol": 0.5, "pan": 0.55,
         "notes": bass(_TOWN, 3, 1.0, 2)}]},
    "route": {"bpm": 132, "loop": True, "tracks": [
        {"inst": "pulse50", "vol": 0.42, "pan": 0.5,
         "notes": arp(_ROUTE, [0, 2, 1, 2, 0, 2, 1, 2], 5, 0.25)},
        {"inst": "tri", "vol": 0.5, "pan": 0.5,
         "notes": bass(_ROUTE, 3, 0.5, 4)},
        {"inst": "drum", "vol": 0.5, "pan": 0.5,
         "notes": drums(["K", "H", "S", "H"] * 4, 0.5)}]},
    "battle_wild": {"bpm": 150, "loop": True, "tracks": [
        {"inst": "pulse25", "vol": 0.45, "pan": 0.5,
         "notes": arp(_BATTLE, [0, 1, 2, 1, 0, 2, 1, 2], 5, 0.25)},
        {"inst": "tri", "vol": 0.55, "pan": 0.5,
         "notes": bass(_BATTLE, 2, 0.25, 8)},
        {"inst": "drum", "vol": 0.55, "pan": 0.5,
         "notes": drums(["K", "H", "K", "H", "S", "H", "K", "H"] * 4, 0.25)}]},
    "battle_trainer": {"bpm": 168, "loop": True, "tracks": [
        {"inst": "pulse25", "vol": 0.45, "pan": 0.5,
         "notes": arp(_BATTLE, [0, 2, 1, 2, 3, 2, 1, 0], 5, 0.25)},
        {"inst": "saw", "vol": 0.30, "pan": 0.5,
         "notes": arp(_BATTLE, [0], 4, 1.0)},
        {"inst": "tri", "vol": 0.55, "pan": 0.5,
         "notes": bass(_BATTLE, 2, 0.25, 8)},
        {"inst": "drum", "vol": 0.6, "pan": 0.5,
         "notes": drums(["K", "H", "S", "H"] * 8, 0.25)}]},
    "victory": {"bpm": 140, "loop": False, "tracks": [
        {"inst": "pulse50", "vol": 0.5, "pan": 0.5,
         "notes": [("g5", 0.2), ("g5", 0.2), ("g5", 0.2), ("g5", 0.6),
                   ("e5", 0.6), ("f5", 0.4), ("g5", 0.8)]},
        {"inst": "tri", "vol": 0.5, "pan": 0.5,
         "notes": bass([("C", "maj"), ("C", "maj")], 3, 1.0, 2)}]},
    "heal": {"bpm": 120, "loop": False, "tracks": [
        {"inst": "tri", "vol": 0.5, "pan": 0.5,
         "notes": [("c5", 0.5), ("e5", 0.5), ("g5", 0.5), ("c6", 1.0)]}]},
}


def _pad(buf, n):
    return np.concatenate([buf, np.zeros(n - len(buf))]) if len(buf) < n else buf[:n]


def _instrument(inst, tok, dur, rng):
    if inst == "drum":
        n = _n(dur)
        if tok == "K":                                  # kick: pitch-drop thump
            return _pad(_slide(150, 50, min(dur, 0.18), "tri"), n)
        if tok == "S":                                  # snare: noise burst
            d = min(dur, 0.12)
            return _pad(0.9 * noise(d, rng) * envelope(_n(d), release=0.08), n)
        if tok == "H":                                  # hat: short noise tick
            d = min(dur, 0.04)
            return _pad(0.5 * noise(d, rng) * envelope(_n(d)), n)
        return np.zeros(n)
    f = _freq(tok)
    if inst == "pulse25":
        return square(f, dur, 0.25)
    if inst == "pulse50":
        return square(f, dur, 0.5)
    if inst == "saw":
        return saw(f, dur)
    if inst == "sine":
        return sine(f, dur)
    return triangle(f, dur)             # 'tri' / default


def render_song(name):
    song = SONGS[name]
    beat = 60.0 / song["bpm"]
    rng = np.random.RandomState(hash(name) & 0x7FFFFFFF)
    rendered = []
    for tr in song["tracks"]:
        chunks = []
        for tok, beats in tr["notes"]:
            dur = beats * beat
            w = _instrument(tr["inst"], tok, dur, rng)
            env = (np.ones(len(w)) if tr["inst"] == "drum"
                   else envelope(len(w), attack=0.005,
                                 release=min(0.05, dur * 0.4)))
            chunks.append(w[:len(env)] * env * tr.get("vol", 0.5))
        rendered.append((np.concatenate(chunks) if chunks else np.zeros(1),
                         tr.get("pan", 0.5)))
    length = max(len(t) for t, _ in rendered)
    left = np.zeros(length)
    right = np.zeros(length)
    for track, pan in rendered:
        if len(track) < length:
            track = np.pad(track, (0, length - len(track)))
        left += track * math.sqrt(1.0 - pan)
        right += track * math.sqrt(pan)
    peak = max(float(np.abs(left).max()), float(np.abs(right).max()), 1e-6)
    return np.column_stack([left / peak, right / peak]) * 0.85


def _song_sound(name):
    stereo = render_song(name)
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    if CHANNELS == 1:
        data = data.mean(axis=1).astype(np.int16)
    return pygame.sndarray.make_sound(np.ascontiguousarray(data))


# ── MIDI export (Standard MIDI File, format 1) ───────────────────────
_GM = {"pulse25": 80, "pulse50": 80, "saw": 81, "sine": 80, "tri": 38}
_DRUM_NOTE = {"K": 36, "S": 38, "H": 42}


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _mtrk(events):
    body = b"".join(_vlq(d) + e for d, e in events) + _vlq(0) + b"\xFF\x2F\x00"
    return b"MTrk" + struct.pack(">I", len(body)) + body


def export_song_midi(name, path, division=480):
    song = SONGS[name]
    tempo = struct.pack(">I", int(60_000_000 / song["bpm"]))[1:]
    tracks = [_mtrk([(0, b"\xFF\x51\x03" + tempo)])]
    for ti, tr in enumerate(song["tracks"]):
        is_drum = tr["inst"] == "drum"
        ch = 9 if is_drum else (ti % 15 + (1 if ti % 15 >= 9 else 0)) % 16
        vel = int(max(1, min(127, tr.get("vol", 0.5) * 127)))
        events = []
        if not is_drum:
            events.append((0, bytes([0xC0 | ch, _GM.get(tr["inst"], 80)])))
        for tok, beats in tr["notes"]:
            ticks = int(beats * division)
            note = (_DRUM_NOTE.get(tok) if is_drum
                    else (None if _freq(tok) <= 0 else
                          (tok if isinstance(tok, int) else note_midi(tok))))
            if note is None:
                events.append((ticks, b"\x90" if False else b""))   # rest
                events[-1] = (ticks, b"")
                continue
            events.append((0, bytes([0x90 | ch, note, vel])))
            events.append((ticks, bytes([0x80 | ch, note, 0])))
    # collapse empty rest markers into the following delta
        events = _absorb_rests(events)
        tracks.append(_mtrk(events))
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), division)
    with open(path, "wb") as f:
        f.write(header)
        for t in tracks:
            f.write(t)
    return path


def _absorb_rests(events):
    out = []
    carry = 0
    for delta, data in events:
        if data == b"":               # a rest: push its delta onto the next event
            carry += delta
            continue
        out.append((delta + carry, data))
        carry = 0
    if carry and out:                 # trailing rest -> extend nothing; drop
        pass
    return out


def export_songs_to_midi(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    return [export_song_midi(name, os.path.join(out_dir, f"{name}.mid"))
            for name in SONGS]


# ── the manager wired into the game ──────────────────────────────────
_MUSIC_EXTS = (".ogg", ".mp3", ".wav", ".mid", ".midi")


class AudioManager:
    def __init__(self, game_dir="", *, manifest=None, mute=False):
        global RATE, CHANNELS
        self.enabled = False
        self._sfx_cache = {}
        self._cry_cache = {}
        self._song_cache = {}
        self._music_name = None
        self._music_is_file = False
        m = (manifest or {}).get("settings", {})
        self.master = float(m.get("audio_volume", 0.7))
        self.music_volume = float(m.get("music_volume", 0.6))
        self.sfx_volume = float(m.get("sfx_volume", 0.8))
        self.midi = bool(m.get("midi", False))      # play external .mid files?
        self.muted = bool(mute)
        self.audio_dir = os.path.join(game_dir, "audio") if game_dir else ""
        if pygame is None:
            return
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(44100, -16, 2, 512)
            init = pygame.mixer.get_init()
        except Exception:
            init = None
        if not init:
            return
        RATE, _, CHANNELS = init
        try:
            pygame.mixer.set_num_channels(16)
            pygame.mixer.set_reserved(2)            # 0 = music, 1 = cries
            self._music_chan = pygame.mixer.Channel(0)
            self._cry_chan = pygame.mixer.Channel(1)
        except Exception:
            return
        self.enabled = True

    # ── settings ──
    def set_muted(self, muted: bool) -> None:
        self.muted = bool(muted)
        if not self.enabled:
            return
        if self.muted:
            self._music_chan.set_volume(0.0)
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(0.0)
        else:
            self._apply_music_volume()

    def toggle_mute(self) -> bool:
        self.set_muted(not self.muted)
        return self.muted

    def _apply_music_volume(self):
        v = 0.0 if self.muted else self.music_volume * self.master
        self._music_chan.set_volume(v)
        try:
            pygame.mixer.music.set_volume(v)
        except Exception:
            pass

    # ── sfx + cries ──
    def play_sfx(self, name: str) -> None:
        if not self.enabled or self.muted or not name:
            return
        snd = self._sfx_cache.get(name)
        if snd is None:
            rng = np.random.RandomState(abs(hash(name)) & 0x7FFFFFFF)
            snd = _to_sound(_sfx(name, rng))
            self._sfx_cache[name] = snd
        snd.set_volume(self.sfx_volume * self.master)
        snd.play()

    def play_cry(self, seed) -> None:
        if not self.enabled or self.muted or seed in (None, 0):
            return
        snd = self._cry_cache.get(seed)
        if snd is None:
            snd = _to_sound(cry_buffer(seed))
            self._cry_cache[seed] = snd
        snd.set_volume(min(1.0, self.sfx_volume * self.master * 1.1))
        self._cry_chan.play(snd)

    # ── music ──
    def _find_music_file(self, name):
        if not self.audio_dir:
            return None
        for ext in _MUSIC_EXTS:
            p = os.path.join(self.audio_dir, "music", name + ext)
            if os.path.exists(p):
                if ext in (".mid", ".midi") and not self.midi:
                    continue
                return p
        return None

    def play_music(self, name: str, loop: bool = True) -> None:
        if not self.enabled or not name:
            return
        if self._music_name == name and self._is_music_busy():
            return
        path = self._find_music_file(name)
        if path:
            try:
                self._music_chan.stop()
                pygame.mixer.music.load(path)
                pygame.mixer.music.set_volume(
                    0.0 if self.muted else self.music_volume * self.master)
                pygame.mixer.music.play(-1 if loop else 0)
                self._music_name, self._music_is_file = name, True
                return
            except Exception:
                pass                                # fall through to synth
        snd = self._song_cache.get(name)
        if snd is None:
            if name not in SONGS:
                return
            snd = _song_sound(name)
            self._song_cache[name] = snd
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._music_chan.set_volume(
            0.0 if self.muted else self.music_volume * self.master)
        self._music_chan.play(snd, loops=-1 if loop else 0)
        self._music_name, self._music_is_file = name, False

    def _is_music_busy(self):
        if self._music_is_file:
            try:
                return pygame.mixer.music.get_busy()
            except Exception:
                return False
        return self._music_chan.get_busy()

    def stop_music(self) -> None:
        if not self.enabled:
            return
        self._music_chan.stop()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._music_name = None
