"""Sinais de imagem numa unica passada: corte de cena, movimento, flash
e o perfil horizontal da acao (usado depois pra reenquadrar em 9:16)."""
from __future__ import annotations

import numpy as np

from .. import media

LARG, ALT = 320, 180
COLUNAS = 32          # o quadro vira 32 faixas verticais de energia


def _cinza(q: np.ndarray) -> np.ndarray:
    return (0.299 * q[:, :, 0] + 0.587 * q[:, :, 1] + 0.114 * q[:, :, 2]).astype(np.float32)


def extrair(caminho: str, duracao: float, fps_amostra: float = 4.0,
            ffmpeg: str = "ffmpeg", progresso=None) -> dict:
    segundos = max(1, int(np.ceil(duracao)))
    mov = np.zeros(segundos, np.float32)
    flash = np.zeros(segundos, np.float32)
    corte = np.zeros(segundos, np.float32)
    contador = np.zeros(segundos, np.float32)

    total_quadros = int(duracao * fps_amostra) or 1
    perfil = np.zeros((total_quadros + 2, COLUNAS), np.float32)
    brilho_col = np.zeros((total_quadros + 2, COLUNAS), np.float32)
    cortes: list[float] = []

    ant = None
    hist_ant = None
    i = 0
    largura_faixa = LARG // COLUNAS

    for q in media.quadros(caminho, fps_amostra, LARG, ALT, ffmpeg=ffmpeg):
        t = i / fps_amostra
        s = min(segundos - 1, int(t))
        g = _cinza(q)

        if ant is not None:
            d = np.abs(g - ant)
            mov[s] += float(d.mean())
            flash[s] += abs(float(g.mean() - ant.mean()))
            # energia de movimento por faixa vertical, pro reenquadre
            faixas = d[:, :COLUNAS * largura_faixa].reshape(ALT, COLUNAS, largura_faixa)
            perfil[i] = faixas.mean(axis=(0, 2))
        gf = g[:, :COLUNAS * largura_faixa].reshape(ALT, COLUNAS, largura_faixa)
        brilho_col[i] = gf.mean(axis=(0, 2))

        hist = np.histogram(g, bins=32, range=(0, 255))[0].astype(np.float32)
        hist /= hist.sum() + 1e-9
        if hist_ant is not None:
            qui = float(((hist - hist_ant) ** 2 / (hist + hist_ant + 1e-9)).sum())
            corte[s] = max(corte[s], qui)
            if qui > 0.35:
                cortes.append(round(t, 2))
        hist_ant = hist

        ant = g
        contador[s] += 1
        i += 1
        if progresso and i % 600 == 0:
            progresso(min(0.99, i / max(1, total_quadros)), "lendo a imagem")

    contador = np.maximum(contador, 1)
    mov /= contador
    flash /= contador

    # junta cortes colados (a mesma virada contada duas vezes)
    limpos: list[float] = []
    for c in cortes:
        if not limpos or c - limpos[-1] > 0.6:
            limpos.append(c)

    return {
        "movimento": mov,
        "flash": flash,
        "corte_cena": corte,
        "cortes": limpos,
        "perfil_acao": perfil[:max(1, i)],
        "perfil_brilho": brilho_col[:max(1, i)],
        "fps_perfil": fps_amostra,
    }
