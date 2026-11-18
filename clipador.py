#!/usr/bin/env python3
"""Clipador. Roda local no Mac e abre a tela no navegador."""
from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import config, servidor  # noqa: E402

PORTA = 8777


def main() -> None:
    plat = config.detectar()
    print("Clipador")
    print("  " + plat.resumo()["descricao"])
    if not plat.ffmpeg:
        print("\n  Falta o ffmpeg. Roda o instalar.command de novo.\n")
        return
    if plat.transcritor == "nenhum":
        print("  Aviso: sem transcricao instalada, os clipes saem sem legenda.")
    s = servidor.subir(PORTA)
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
