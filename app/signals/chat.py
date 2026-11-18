"""Sinal de chat: o melhor indicador de momento bom numa live brasileira."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

RISADA = re.compile(r"(k{3,}|ha{2,}|rsrs|lmao|lul|kekw|omegalul|pepelaugh|\U0001F602|\U0001F923)", re.I)
SUSTO = re.compile(r"(nossa|caralho|mano|que isso|pelo amor|eita|aff|meu deus|pqp|wtf|omg|poggers|pog\b)", re.I)
PEDIDO = re.compile(r"(clipa|clipar|clip\b|corta isso|manda pro tiktok|isso ai)", re.I)


def carregar(arquivo: Path) -> list[dict]:
    if not arquivo.exists():
        return []
    msgs = []
    for linha in arquivo.read_text("utf-8", errors="ignore").splitlines():
        try:
            msgs.append(json.loads(linha))
        except Exception:
            continue
    return msgs


def extrair(mensagens: list[dict], inicio_epoch: float, duracao: float) -> dict[str, np.ndarray]:
    segundos = max(1, int(np.ceil(duracao)))
    taxa = np.zeros(segundos, np.float32)
    risada = np.zeros(segundos, np.float32)
    susto = np.zeros(segundos, np.float32)
    pedido = np.zeros(segundos, np.float32)
    caixa_alta = np.zeros(segundos, np.float32)

    for m in mensagens:
        s = int(m.get("t", 0) - inicio_epoch)
        if s < 0 or s >= segundos:
            continue
        txt = m.get("texto", "")
        taxa[s] += 1
        if RISADA.search(txt):
            risada[s] += 1
        if SUSTO.search(txt):
            susto[s] += 1
        if PEDIDO.search(txt):
            pedido[s] += 1
        letras = [c for c in txt if c.isalpha()]
        if len(letras) >= 4 and sum(c.isupper() for c in letras) / len(letras) > 0.7:
            caixa_alta[s] += 1

    return {
        "chat_taxa": taxa,
        "chat_risada": risada,
        "chat_susto": susto,
        "chat_pedido": pedido,
        "chat_caixa_alta": caixa_alta,
    }
