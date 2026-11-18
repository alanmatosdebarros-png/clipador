"""Junta todos os sinais numa curva so e acha os picos (os momentos)."""
from __future__ import annotations

import numpy as np

MAPA_PESO = {
    "chat_taxa": "chat", "chat_risada": "chat", "chat_susto": "chat",
    "chat_pedido": "marcador", "chat_caixa_alta": "chat",
    "volume": "audio", "subida": "audio", "grave": "flash",
    "voz": "voz",
    "movimento": "movimento", "flash": "flash",
    "evento_jogo": "evento_jogo", "procurado": "evento_jogo", "dano": "evento_jogo",
    "marcador": "marcador",
}

PESO_INTERNO = {
    "chat_taxa": 1.0, "chat_risada": 1.2, "chat_susto": 0.9,
    "chat_pedido": 1.0, "chat_caixa_alta": 0.6,
    "volume": 0.5, "subida": 1.0, "voz": 1.0, "grave": 0.8,
    "movimento": 1.0, "flash": 0.8,
    "evento_jogo": 1.0, "procurado": 0.8, "dano": 0.7, "marcador": 1.0,
}


def normalizar(v: np.ndarray) -> np.ndarray:
    if v.size == 0 or not np.isfinite(v).any():
        return np.zeros_like(v)
    v = np.nan_to_num(v.astype(np.float32))
    base, teto = np.percentile(v, 55), np.percentile(v, 98)
    if teto - base < 1e-6:
        return np.zeros_like(v)
    return np.clip((v - base) / (teto - base), 0, 1)


def _suavizar(v: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    raio = max(1, int(sigma * 3))
    x = np.arange(-raio, raio + 1, dtype=np.float32)
    k = np.exp(-(x ** 2) / (2 * sigma ** 2))
    k /= k.sum()
    return np.convolve(v, k, mode="same")


def fundir(sinais: dict[str, np.ndarray], pesos: dict[str, float],
           segundos: int) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    norm: dict[str, np.ndarray] = {}
    total = np.zeros(segundos, np.float32)
    soma_peso = 0.0
    for nome, v in sinais.items():
        if not isinstance(v, np.ndarray) or v.ndim != 1:
            continue
        if v.size < segundos:
            v = np.pad(v, (0, segundos - v.size))
        v = v[:segundos]
        n = normalizar(v)
        norm[nome] = n
        grupo = MAPA_PESO.get(nome)
        if grupo is None:
            continue
        p = float(pesos.get(grupo, 0.5)) * PESO_INTERNO.get(nome, 1.0)
        total += n * p
        soma_peso += p
    if soma_peso > 0:
        total /= soma_peso
    return _suavizar(total, 2.0), norm


def picos(curva: np.ndarray, intervalo_minimo: int, maximo: int,
          piso_percentil: float = 80.0, borda: int = 5) -> list[int]:
    if curva.size == 0:
        return []
    # as bordas do arquivo dao pico falso (o decodificador entrando e saindo)
    curva = curva.copy()
    if curva.size > borda * 3:
        curva[:borda] = 0.0
        curva[-borda:] = 0.0
    piso = max(float(np.percentile(curva, piso_percentil)), 0.45 * float(curva.max()))
    ordem = np.argsort(curva)[::-1]
    escolhidos: list[int] = []
    for i in ordem:
        if curva[i] < piso:
            break
        if all(abs(int(i) - j) >= intervalo_minimo for j in escolhidos):
            escolhidos.append(int(i))
        if len(escolhidos) >= maximo:
            break
    return sorted(escolhidos)


def explicar(norm: dict[str, np.ndarray], t: int, janela: int = 6) -> dict[str, float]:
    """O que puxou esse momento, pra mostrar na tela."""
    saida: dict[str, float] = {}
    rotulos = {
        "chat_taxa": "chat acelerou", "chat_risada": "chat riu",
        "chat_susto": "chat se assustou", "chat_pedido": "pediram clipe",
        "chat_caixa_alta": "chat em caixa alta",
        "subida": "voce levantou a voz", "volume": "audio alto",
        "voz": "fala animada", "grave": "estouro grave",
        "movimento": "muito movimento", "flash": "clarao na tela",
        "evento_jogo": "evento do jogo", "procurado": "nivel de procurado subiu",
        "dano": "voce tomou dano", "marcador": "momento marcado",
    }
    a, b = max(0, t - janela), t + janela
    for nome, v in norm.items():
        if nome not in rotulos:
            continue
        pico = float(v[a:b].max()) if v[a:b].size else 0.0
        if pico > 0.35:
            saida[rotulos[nome]] = round(pico, 2)
    return dict(sorted(saida.items(), key=lambda kv: -kv[1])[:4])


def sem_sobreposicao(itens: list[dict], fatia_maxima: float = 0.35) -> list[dict]:
    """Tira clipes que se cobrem demais, mantendo o de nota mais alta."""
    ordenados = sorted(itens, key=lambda c: -c["nota"])
    mantidos: list[dict] = []
    for c in ordenados:
        conflito = False
        for m in mantidos:
            ini = max(c["inicio"], m["inicio"])
            fim = min(c["fim"], m["fim"])
            comum = max(0.0, fim - ini)
            menor = min(c["fim"] - c["inicio"], m["fim"] - m["inicio"]) or 1.0
            if comum / menor > fatia_maxima:
                conflito = True
                break
        if not conflito:
            mantidos.append(c)
    return sorted(mantidos, key=lambda c: c["inicio"])
