"""Claude escolhe o que vale clipe e escreve titulo, legenda e hashtags.

Funciona sem chave tambem: ai o app usa modelo de texto proprio, mais simples.
"""
from __future__ import annotations

import json
import re

SISTEMA = """Voce ajuda um streamer brasileiro a transformar trechos de live de GTA em clipes
de TikTok, Reels e Shorts. Recebe trechos com a transcricao do que ele falou e os sinais
que marcaram o momento. Para cada trecho devolve:
- vale: 0 a 100, o quanto aquilo prende alguem que nao conhece o canal
- titulo: ate 8 palavras, sem ponto final, do jeito que o publico fala, nada de "confira" ou "veja"
- legenda: uma ou duas frases curtas pro post, reativa, nada descritiva da cena
- hashtags: 4 a 6, em minusculo, sem acento, misturando jogo e nicho
Nada de emoji com tom de pele. Nada de travessao. Responda so com JSON valido."""


def _sem_chave(trechos: list[dict]) -> list[dict]:
    saida = []
    for t in trechos:
        sinais = list((t.get("sinais") or {}).keys())
        base = sinais[0] if sinais else "momento da live"
        fala = (t.get("transcricao") or "").strip()
        primeiro = re.split(r"[.!?]", fala)[0][:52].strip().lower() if fala else ""
        titulo = primeiro or base
        saida.append({
            "indice": t["indice"],
            "vale": int(min(100, round(float(t.get("nota", 0.5)) * 100))),
            "titulo": titulo,
            "legenda": (primeiro or base).capitalize(),
            "hashtags": ["gta", "gta6", "twitch", "clipes", "gameplay"],
        })
    return saida


def avaliar(trechos: list[dict], chave: str, modelo: str = "claude-sonnet-4-5") -> list[dict]:
    if not chave or not trechos:
        return _sem_chave(trechos)
    corpo = {
        "model": modelo,
        "max_tokens": 2000,
        "system": SISTEMA,
        "messages": [{
            "role": "user",
            "content": "Trechos:\n" + json.dumps(trechos, ensure_ascii=False, indent=1) +
                       '\n\nResponda: {"clipes":[{"indice":0,"vale":0,"titulo":"","legenda":"","hashtags":[]}]}',
        }],
    }
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(corpo).encode("utf-8"),
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            dados_resp = json.loads(resp.read().decode("utf-8"))
        texto = "".join(b.get("text", "") for b in dados_resp.get("content", []))
        bruto = texto[texto.index("{"): texto.rindex("}") + 1]
        dados = json.loads(bruto)
        itens = dados.get("clipes") or []
        if itens:
            return itens
    except Exception:
        pass
    return _sem_chave(trechos)
