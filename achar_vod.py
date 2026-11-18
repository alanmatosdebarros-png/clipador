#!/usr/bin/env python3
"""Acha o VOD mais novo do canal que ainda nao foi clipado.

Escreve no GITHUB_OUTPUT:
    vod=<url>   (vazio quando nao tem nada novo)
    titulo=<titulo do VOD>
    id=<id do VOD>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
CANAL = AQUI / "canal.txt"
FEITOS = AQUI / "processados.txt"


def saida(**campos: str) -> None:
    arq = os.environ.get("GITHUB_OUTPUT")
    linhas = [f"{k}={v}" for k, v in campos.items()]
    if arq:
        with open(arq, "a", encoding="utf-8") as f:
            f.write("\n".join(linhas) + "\n")
    for l in linhas:
        print(l)


def main() -> int:
    canal = ""
    if CANAL.exists():
        for linha in CANAL.read_text("utf-8").splitlines():
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                canal = linha.lstrip("@")
                break
    if not canal:
        print("  sem canal configurado em canal.txt, nada a fazer")
        saida(vod="", titulo="", id="")
        return 0

    print(f"  procurando VOD novo no canal {canal}")
    r = subprocess.run(
        ["yt-dlp", "-J", "--flat-playlist", "--no-warnings", "--playlist-end", "3",
         f"https://www.twitch.tv/{canal}/videos"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"  nao consegui listar os VODs: {r.stderr.strip()[-200:]}")
        saida(vod="", titulo="", id="")
        return 0

    try:
        entradas = json.loads(r.stdout).get("entries") or []
    except Exception:
        entradas = []
    if not entradas:
        print("  nenhum VOD guardado no canal")
        saida(vod="", titulo="", id="")
        return 0

    feitos = set()
    if FEITOS.exists():
        feitos = {l.strip() for l in FEITOS.read_text("utf-8").splitlines() if l.strip()}

    for e in entradas:
        vid = str(e.get("id") or "")
        if not vid or vid in feitos:
            continue
        url = e.get("url") or f"https://www.twitch.tv/videos/{vid}"
        titulo = (e.get("title") or "live").replace("\n", " ")[:80]
        print(f"  achei VOD novo: {vid} ({titulo})")
        saida(vod=url, titulo=titulo, id=vid)
        return 0

    print("  os VODs mais recentes ja foram clipados")
    saida(vod="", titulo="", id="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
