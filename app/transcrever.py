"""Transcricao com tempo real de cada palavra.

No Mac usa mlx-whisper (roda no chip, rapido). Fora dele, faster-whisper.
Transcreve uma vez so, por padrao apenas em volta dos candidatos.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from . import media

_modelo_cache: dict[str, object] = {}

LIXO = {
    "legendas pela comunidade amara.org", "amara.org", "legendado por",
    "obrigado por assistir", "inscreva-se no canal", "thanks for watching",
    "subtitles by the amara.org community",
}


def _e_lixo(texto: str, duracao: float) -> bool:
    """So corta o que e alucinacao conhecida do Whisper, nunca fala curta de verdade."""
    t = texto.strip().lower().rstrip(".!?")
    if not t:
        return True
    if t in LIXO or any(l in t for l in LIXO):
        return True
    # mesma frase repetida muitas vezes num trecho longo
    palavras = t.split()
    if len(palavras) > 12 and len(set(palavras)) <= 3 and duracao > 6:
        return True
    return False


def transcrever(caminho: str, inicio: float, fim: float, cfg: dict,
                motor: str, ffmpeg: str = "ffmpeg") -> dict:
    """Devolve {'texto': str, 'palavras': [{'p','ini','fim'}]} em tempo do clipe."""
    if motor == "nenhum":
        return {"texto": "", "palavras": [], "motor": "nenhum"}

    if motor == "faster":
        # o proprio ffmpeg decodifica; assim nao dependemos do PyAV do
        # faster-whisper, que muda de assinatura entre versoes
        pcm = media.audio_pcm(caminho, 16000, ffmpeg,
                              inicio=inicio, duracao=max(0.5, fim - inicio))
        if pcm.size < 1600:
            return {"texto": "", "palavras": [], "motor": "faster"}
        return _faster(pcm.astype(np.float32), cfg)

    with tempfile.TemporaryDirectory() as tmp:
        wav = media.extrair_wav(caminho, Path(tmp) / "a.wav", 16000, ffmpeg,
                                inicio=inicio, duracao=max(0.5, fim - inicio))
        return _mlx(str(wav), cfg)


def _mlx(wav: str, cfg: dict) -> dict:
    import mlx_whisper
    r = mlx_whisper.transcribe(
        wav,
        path_or_hf_repo=cfg.get("modelo_transcricao", "mlx-community/whisper-small-mlx"),
        language=cfg.get("idioma") or None,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    palavras, partes = [], []
    for seg in r.get("segments", []):
        dur = float(seg.get("end", 0)) - float(seg.get("start", 0))
        if _e_lixo(seg.get("text", ""), dur):
            continue
        partes.append(seg.get("text", "").strip())
        for w in seg.get("words", []) or []:
            palavras.append({"p": str(w.get("word", "")).strip(),
                             "ini": float(w.get("start", 0)),
                             "fim": float(w.get("end", 0))})
    return {"texto": " ".join(partes).strip(), "palavras": palavras, "motor": "mlx"}


def _faster(audio, cfg: dict) -> dict:
    from faster_whisper import WhisperModel
    nome = cfg.get("modelo_transcricao_fallback", "small")
    if nome not in _modelo_cache:
        _modelo_cache[nome] = WhisperModel(nome, device="cpu", compute_type="int8")
    modelo = _modelo_cache[nome]
    segs, _ = modelo.transcribe(audio, language=cfg.get("idioma") or None,  # type: ignore[attr-defined]
                                word_timestamps=True, vad_filter=True,
                                condition_on_previous_text=False)
    palavras, partes = [], []
    for seg in segs:
        if _e_lixo(seg.text, seg.end - seg.start):
            continue
        partes.append(seg.text.strip())
        for w in (seg.words or []):
            palavras.append({"p": w.word.strip(), "ini": float(w.start), "fim": float(w.end)})
    return {"texto": " ".join(partes).strip(), "palavras": palavras, "motor": "faster"}
