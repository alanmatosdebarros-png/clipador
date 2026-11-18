"""Leitura de video e audio via ffmpeg, em fluxo, sem carregar tudo na memoria."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np


@dataclass
class Info:
    duracao: float
    largura: int
    altura: int
    fps: float
    tem_audio: bool


def info(caminho: str | Path, ffprobe: str = "ffprobe") -> Info:
    r = subprocess.run([ffprobe, "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(caminho)],
                       capture_output=True, text=True, timeout=120)
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    if v is None:
        raise RuntimeError("arquivo sem trilha de video")
    num, den = (v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)
    dur = float(d.get("format", {}).get("duration") or v.get("duration") or 0.0)
    return Info(dur, int(v["width"]), int(v["height"]), fps, a is not None)


def quadros(caminho: str | Path, fps: float, largura: int, altura: int,
            ffmpeg: str = "ffmpeg", inicio: float | None = None,
            duracao: float | None = None) -> Iterator[np.ndarray]:
    """Gera quadros RGB ja reduzidos, um por vez."""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if inicio is not None:
        cmd += ["-ss", f"{inicio:.3f}"]
    cmd += ["-i", str(caminho)]
    if duracao is not None:
        cmd += ["-t", f"{duracao:.3f}"]
    cmd += ["-vf", f"fps={fps},scale={largura}:{altura}:flags=fast_bilinear",
            "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    n = largura * altura * 3
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=n * 4)
    try:
        while True:
            cru = p.stdout.read(n)  # type: ignore[union-attr]
            if not cru or len(cru) < n:
                break
            yield np.frombuffer(cru, np.uint8).reshape(altura, largura, 3)
    finally:
        try:
            p.stdout.close()  # type: ignore[union-attr]
        except Exception:
            pass
        p.wait()


def audio_pcm(caminho: str | Path, taxa: int = 16000, ffmpeg: str = "ffmpeg",
              inicio: float | None = None, duracao: float | None = None) -> np.ndarray:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error"]
    if inicio is not None:
        cmd += ["-ss", f"{inicio:.3f}"]
    cmd += ["-i", str(caminho)]
    if duracao is not None:
        cmd += ["-t", f"{duracao:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(taxa), "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=None)
    if not r.stdout:
        return np.zeros(0, np.float32)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0


def extrair_wav(caminho: str | Path, destino: Path, taxa: int = 16000,
                ffmpeg: str = "ffmpeg", inicio: float | None = None,
                duracao: float | None = None) -> Path:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
    if inicio is not None:
        cmd += ["-ss", f"{inicio:.3f}"]
    cmd += ["-i", str(caminho)]
    if duracao is not None:
        cmd += ["-t", f"{duracao:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", str(taxa), "-c:a", "pcm_s16le", str(destino)]
    subprocess.run(cmd, check=True, capture_output=True)
    return destino


def medir_loudness(caminho: str | Path, inicio: float, fim: float,
                   ffmpeg: str = "ffmpeg") -> dict:
    """Primeira passada do loudnorm (EBU R128), pra equalizar o volume de verdade."""
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-ss", f"{inicio:.3f}",
           "-t", f"{max(0.1, fim - inicio):.3f}", "-i", str(caminho),
           "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    txt = r.stderr
    try:
        bruto = txt[txt.rindex("{"): txt.rindex("}") + 1]
        return json.loads(bruto)
    except Exception:
        return {}
