#!/usr/bin/env python3
"""Monta o texto do lote de clipes (titulo, legenda e hashtags de cada um)."""
import json
import pathlib
import sys

titulo = sys.argv[1] if len(sys.argv) > 1 else "live"
linhas = [f"Clipes de: {titulo}", "",
          "Baixe os MP4 em Assets, aqui embaixo. Cada clipe tem uma capa .jpg",
          "com o mesmo numero.", ""]
arq = pathlib.Path("saida/textos.json")
if arq.exists():
    for i, c in enumerate(json.loads(arq.read_text("utf-8")), 1):
        tags = " ".join("#" + h for h in c.get("hashtags", []))
        linhas += [f"**{i}. {c.get('titulo','')}**", "",
                   f"{c.get('legenda','')} {tags}".strip(), ""]
pathlib.Path("corpo.md").write_text("\n".join(linhas) + "\n", "utf-8")
print(f"corpo.md com {len(linhas)} linhas")
