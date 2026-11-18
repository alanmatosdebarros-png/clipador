"""Escolhe onde cada clipe comeca e termina.

Alvo de 2min30, mas respira: comeca no corte de cena antes do sinal subir
e termina depois do desfecho. Preso entre o minimo e o maximo.
"""
from __future__ import annotations

import numpy as np


def _mais_perto(valores: list[float], alvo: float, tolerancia: float) -> float | None:
    if not valores:
        return None
    arr = np.asarray(valores, np.float32)
    i = int(np.argmin(np.abs(arr - alvo)))
    return float(arr[i]) if abs(arr[i] - alvo) <= tolerancia else None


def limites(pico: int, curva: np.ndarray, cortes_cena: list[float],
            duracao_total: float, alvo: float = 150.0,
            minimo: float = 45.0, maximo: float = 180.0,
            posicao_pico: float = 0.62) -> tuple[float, float]:
    n = curva.size
    base = float(np.percentile(curva, 60))

    # anda pra tras ate o sinal cair abaixo da base e ficar
    ini = pico
    quietos = 0
    while ini > 0 and pico - ini < maximo:
        ini -= 1
        quietos = quietos + 1 if curva[ini] < base else 0
        if quietos >= 3:
            break
    inicio = float(max(0, ini))

    # anda pra frente ate o desfecho, mais 2s de folga
    fim_i = pico
    quietos = 0
    while fim_i < n - 1 and fim_i - pico < maximo:
        fim_i += 1
        quietos = quietos + 1 if curva[fim_i] < base else 0
        if quietos >= 2:
            break
    fim = float(min(duracao_total, fim_i + 2))

    dur = fim - inicio

    # curto demais: abre em volta do pico, deixando ele a 62% do clipe
    if dur < minimo:
        antes = alvo * posicao_pico if alvo <= maximo else minimo * posicao_pico
        antes = min(antes, minimo * posicao_pico)
        inicio = max(0.0, pico - antes)
        fim = min(duracao_total, inicio + minimo)
        inicio = max(0.0, fim - minimo)

    # longo demais: corta pela frente, mantendo o pico no mesmo lugar relativo
    dur = fim - inicio
    if dur > maximo:
        inicio = max(0.0, pico - maximo * posicao_pico)
        fim = min(duracao_total, inicio + maximo)
        inicio = max(0.0, fim - maximo)

    # puxa pro alvo de 2min30 quando da, sem estourar o que ja foi decidido
    dur = fim - inicio
    if dur < alvo <= maximo:
        falta = alvo - dur
        novo_inicio = max(0.0, inicio - falta * posicao_pico)
        novo_fim = min(duracao_total, fim + (falta - (inicio - novo_inicio)))
        inicio, fim = novo_inicio, novo_fim

    # encaixa o comeco num corte de cena, se tiver um pertinho
    encaixe = _mais_perto(cortes_cena, inicio, 2.0)
    if encaixe is not None and encaixe < pico - minimo * 0.4:
        inicio = encaixe

    inicio = max(0.0, round(inicio, 2))
    fim = min(duracao_total, round(max(inicio + minimo, fim), 2))
    return inicio, fim
