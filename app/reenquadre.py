"""Reenquadre 16:9 -> 9:16 seguindo a acao, com caminho suavizado.

Usa o perfil horizontal de movimento que ja foi calculado na leitura da imagem,
entao nao decodifica o video de novo. O corte so pula de lugar na virada de cena.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np


def caminho(perfil_acao: np.ndarray, perfil_brilho: np.ndarray, fps_perfil: float,
            inicio: float, fim: float, largura_fonte: int, largura_corte: int,
            cortes_cena: list[float], forca_centro: float = 0.45,
            zona_morta: float = 0.03, suavidade: float = 0.08) -> list[tuple[float, int]]:
    colunas = perfil_acao.shape[1] if perfil_acao.size else 32
    a = int(inicio * fps_perfil)
    b = max(a + 1, int(fim * fps_perfil))
    trecho = perfil_acao[a:b] if perfil_acao.size else np.zeros((b - a, colunas), np.float32)
    brilho = perfil_brilho[a:b] if perfil_brilho.size else np.zeros_like(trecho)

    centros = np.linspace(0.5 / colunas, 1 - 0.5 / colunas, colunas, dtype=np.float32)
    # prior de centro: o jogo quase sempre importa mais no meio da tela
    prior = np.exp(-((centros - 0.5) ** 2) / (2 * 0.30 ** 2)).astype(np.float32)

    x_max = max(0, largura_fonte - largura_corte)
    meio = 0.5
    atual = meio
    pontos: list[tuple[float, int]] = []
    cortes = [c for c in cortes_cena if inicio <= c <= fim]
    prox_corte = 0

    for i in range(trecho.shape[0]):
        t = i / fps_perfil
        energia = trecho[i] * prior
        if energia.sum() < 1e-6:
            energia = brilho[i] * prior
        alvo = float((energia * centros).sum() / (energia.sum() + 1e-9)) if energia.sum() > 1e-9 else meio
        alvo = forca_centro * meio + (1 - forca_centro) * alvo

        virou = False
        while prox_corte < len(cortes) and cortes[prox_corte] - inicio <= t:
            virou = True
            prox_corte += 1

        if virou:
            atual = alvo                       # na virada de cena pode pular
        elif abs(alvo - atual) > zona_morta:   # fora da zona morta, acompanha devagar
            atual += (alvo - atual) * suavidade

        x = int(round(np.clip(atual * largura_fonte - largura_corte / 2, 0, x_max)))
        pontos.append((round(t, 3), x))

    if not pontos:
        pontos = [(0.0, x_max // 2)]
    return pontos


def escrever_sendcmd(pontos: list[tuple[float, int]], destino: Path,
                     passo_minimo: int = 1) -> Path:
    linhas, ultimo = [], None
    for t, x in pontos:
        if ultimo is None or abs(x - ultimo) >= passo_minimo:
            linhas.append(f"{t:.3f} crop x {x};")
            ultimo = x
    if not linhas:
        linhas = ["0.000 crop x 0;"]
    destino.write_text("\n".join(linhas) + "\n", "utf-8")
    return destino


def regiao_px(r: dict | None, largura: int, altura: int) -> tuple[int, int, int, int] | None:
    if not r:
        return None
    x = int(r["x"] * largura) // 2 * 2
    y = int(r["y"] * altura) // 2 * 2
    w = max(2, int(r["w"] * largura) // 2 * 2)
    h = max(2, int(r["h"] * altura) // 2 * 2)
    w = min(w, largura - x)
    h = min(h, altura - y)
    return (x, y, w, h)
