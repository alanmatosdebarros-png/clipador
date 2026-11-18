#!/usr/bin/env python3
"""Clipador. Roda local no Mac e abre a tela no navegador."""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config, servidor  # noqa: E402

PORTA = int(os.environ.get("CLIPADOR_PORTA", "8777"))
HOST = os.environ.get("CLIPADOR_HOST", "127.0.0.1")
NA_NUVEM = bool(os.environ.get("CODESPACES") or os.environ.get("CLIPADOR_NUVEM"))


def main() -> None:
    plat = config.detectar()
    print("Clipador")
    print("  " + plat.resumo()["descricao"])
    if not plat.ffmpeg:
        print("\n  Falta o ffmpeg. Roda o instalar.command de novo.\n")
        return
    if plat.transcritor == "nenhum":
        print("  Aviso: sem transcricao instalada, os clipes saem sem legenda.")
    s = servidor.subir(PORTA, HOST)
    if NA_NUVEM:
        print(f"\n  rodando na nuvem. A aba da porta {PORTA} abre sozinha;")
        print("  se nao abrir, va na aba PORTS e clique no cadeado/globo da porta.\n")
    else:
        url = f"http://127.0.0.1:{PORTA}/"
        print(f"\n  tela em {url}\n  pra fechar, Ctrl+C\n")
        threading.Thread(target=lambda: (time.sleep(1), webbrowser.open(url)), daemon=True).start()
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\n  fechando")
        servidor.TRABALHO.parar()
        s.shutdown()


if __name__ == "__main__":
    main()
