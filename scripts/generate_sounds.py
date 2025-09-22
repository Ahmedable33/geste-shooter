#!/usr/bin/env python3
"""
Generate placeholder WAV sound files for the Gesture Shooting Game.
Files created in gesture_shooter/assets/sounds/:
- shot.wav   : short square burst
- hit.wav    : noise burst with decay
- reload.wav : two short beeps with a brief gap
- dry.wav    : short low-frequency click
"""
from __future__ import annotations

import os
import wave
from pathlib import Path

import numpy as np

SR = 44100  # sample rate


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def tone(freq: float, dur_s: float, vol: float = 0.5, wave_type: str = "sine") -> np.ndarray:
    n = max(1, int(SR * dur_s))
    t = np.linspace(0.0, dur_s, n, endpoint=False, dtype=np.float32)
    if wave_type == "square":
        w = np.sign(np.sin(2 * np.pi * freq * t))
    elif wave_type == "saw":
        w = 2.0 * (t * freq - np.floor(0.5 + t * freq))
    else:
        w = np.sin(2 * np.pi * freq * t)
    # Simple attack/decay envelope to avoid clicks
    attack = int(0.01 * n)
    decay = int(0.05 * n)
    env = np.ones_like(w)
    if attack > 0:
        env[:attack] = np.linspace(0.0, 1.0, attack, dtype=np.float32)
    if decay > 0:
        env[-decay:] = np.linspace(1.0, 0.0, decay, dtype=np.float32)
    a = (w * env * vol).astype(np.float32)
    # stereo
    return np.stack([a, a], axis=1)


def noise(dur_s: float, vol: float = 0.5, decay: bool = True) -> np.ndarray:
    n = max(1, int(SR * dur_s))
    w = np.random.uniform(-1.0, 1.0, size=n).astype(np.float32)
    if decay:
        env = np.exp(-np.linspace(0, 5, n)).astype(np.float32)
        w *= env
    a = (w * vol).astype(np.float32)
    return np.stack([a, a], axis=1)


def silence(dur_s: float) -> np.ndarray:
    n = max(1, int(SR * dur_s))
    return np.zeros((n, 2), dtype=np.float32)


def write_wav(path: Path, data_stereo_float32: np.ndarray) -> None:
    # Clamp and convert to int16
    data = np.clip(data_stereo_float32, -1.0, 1.0)
    pcm = (data * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "gesture_shooter" / "assets" / "sounds"
    ensure_dir(out_dir)

    # shot: short square burst ~0.09s @ 700 Hz
    shot = tone(700.0, 0.09, vol=0.6, wave_type="square")
    write_wav(out_dir / "shot.wav", shot)

    # hit: noise burst ~0.26s with decay
    hit = noise(0.26, vol=0.5, decay=True)
    write_wav(out_dir / "hit.wav", hit)

    # reload: two beeps 0.1s @ 500 Hz separated by 0.08s silence
    reload_ = np.concatenate([
        tone(500.0, 0.10, vol=0.45, wave_type="sine"),
        silence(0.08),
        tone(500.0, 0.10, vol=0.45, wave_type="sine"),
    ], axis=0)
    write_wav(out_dir / "reload.wav", reload_)

    # dry: short low beep ~0.06s @ 180 Hz
    dry = tone(180.0, 0.06, vol=0.5, wave_type="sine")
    write_wav(out_dir / "dry.wav", dry)

    print(f"Generated sounds in {out_dir}")


if __name__ == "__main__":
    main()
