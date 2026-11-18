"""Sinais de audio: volume, voz animada e estouro grave (explosao, tiro)."""
from __future__ import annotations

import numpy as np

TAXA = 16000


def _stft(x: np.ndarray, janela: int, salto: int) -> np.ndarray:
    if len(x) < janela:
        x = np.pad(x, (0, janela - len(x)))
    n = 1 + (len(x) - janela) // salto
    idx = np.arange(janela)[None, :] + salto * np.arange(n)[:, None]
    w = np.hanning(janela).astype(np.float32)
    return np.abs(np.fft.rfft(x[idx] * w, axis=1)).astype(np.float32)


def extrair(pcm: np.ndarray, duracao: float) -> dict[str, np.ndarray]:
    """Devolve sinais numa grade de 1 segundo."""
    segundos = max(1, int(np.ceil(duracao)))
    vazio = np.zeros(segundos, np.float32)
    if pcm.size < TAXA // 2:
        return {"volume": vazio, "voz": vazio, "grave": vazio, "silencio": np.ones(segundos, np.float32)}

    janela, salto = 1024, 320          # 64 ms de janela, 20 ms de salto
    esp = _stft(pcm, janela, salto)
    freqs = np.fft.rfftfreq(janela, 1 / TAXA)
    quadros_por_s = TAXA / salto

    energia = esp.sum(axis=1) + 1e-9
    banda_voz = (freqs >= 300) & (freqs <= 3400)
    banda_grave = freqs <= 120

    volume_q = 20 * np.log10(energia / energia.max())
    voz_q = esp[:, banda_voz].sum(axis=1) / energia
    grave_q = esp[:, banda_grave].sum(axis=1) / energia

    def por_segundo(v: np.ndarray, func) -> np.ndarray:
        saida = np.zeros(segundos, np.float32)
        for s in range(segundos):
            a, b = int(s * quadros_por_s), int((s + 1) * quadros_por_s)
            pedaco = v[a:b]
            saida[s] = func(pedaco) if pedaco.size else saida[max(0, s - 1)]
        return saida

    volume = por_segundo(volume_q, np.max)
    voz = por_segundo(voz_q * (volume_q > -40), np.mean)
    grave = por_segundo(grave_q * (volume_q > -35), np.max)

    # subida rapida de volume vale mais do que volume alto parado
    subida = np.diff(volume, prepend=volume[0])
    subida = np.clip(subida, 0, None)

    silencio = (volume < -45).astype(np.float32)

    return {
        "volume": volume,
        "subida": subida,
        "voz": voz,
        "grave": grave,
        "silencio": silencio,
    }
