"""Audio tools: export the engine's built-in chiptune songs as editable
Standard MIDI Files, list the available songs/SFX, or render preview WAVs.

The game synthesizes everything procedurally at runtime, so audio assets
are optional. Exporting MIDI is the bridge to authoring your own tracks:
edit the .mid files in any DAW/sequencer, drop them in
``<game>/audio/music/<name>.mid``, and set ``"midi": true`` under the
manifest's ``settings`` to have the game play them instead of the synth.

    python -m pkmn.cli.audio --export-midi               # -> game/assets/audio/music
    python -m pkmn.cli.audio --export-midi out/midi
    python -m pkmn.cli.audio --list
    python -m pkmn.cli.audio --render-wav out/wav        # needs the mixer
"""
from __future__ import annotations

import argparse
import os

from ..game import audio


def _export_midi(out_dir: str) -> int:
    paths = audio.export_songs_to_midi(out_dir)
    print(f"wrote {len(paths)} MIDI file(s) to {out_dir}/")
    for p in paths:
        print(f"  {os.path.basename(p)}")
    return 0


def _list() -> int:
    print("songs:")
    for name, song in audio.SONGS.items():
        kind = "loop" if song.get("loop", True) else "once"
        print(f"  {name:16} {song['bpm']:>3} bpm  {len(song['tracks'])} trk  {kind}")
    print("\nsound effects:")
    print("  " + ", ".join(audio.SFX_NAMES))
    return 0


def _render_wav(out_dir: str) -> int:
    """Render each song to a .wav (useful to audition without the game).
    Requires a working mixer; under a dummy driver this still produces
    valid silence-free buffers written via the wave module."""
    import wave

    import numpy as np

    os.makedirs(out_dir, exist_ok=True)
    for name in audio.SONGS:
        stereo = audio.render_song(name)
        data = (np.clip(stereo, -1, 1) * 32767).astype("<i2")
        path = os.path.join(out_dir, f"{name}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(audio.RATE)
            w.writeframes(data.tobytes())
        print(f"  {name}.wav  ({stereo.shape[0] / audio.RATE:.1f}s)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audio tools for the engine.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--export-midi", nargs="?", const="game/assets/audio/music",
                   metavar="DIR", help="write built-in songs as .mid files")
    g.add_argument("--render-wav", metavar="DIR",
                   help="render built-in songs to .wav files")
    g.add_argument("--list", action="store_true",
                   help="list available songs and sound effects")
    args = ap.parse_args(argv)
    if args.list:
        return _list()
    if args.render_wav:
        return _render_wav(args.render_wav)
    return _export_midi(args.export_midi)


if __name__ == "__main__":
    raise SystemExit(main())
