#!/usr/bin/env python3
"""Clipador sem tela: roda na nuvem, do link do VOD ate os MP4 prontos.

Usado pelo GitHub Actions. Tambem roda local:
    python nuvem.py --vod https://twitch.tv/videos/123 --quantos 6
    python nuvem.py --arquivo um_video.mp4 --quantos 2
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from app import config, cortes, ia, media, render, transcrever, twitch
from app.signals import audio as s_audio
from app.signals import fuse
from app.signals import gta as s_gta
from app.signals import vision as s_vision

SAIDA = Path(os.environ.get("CLIPADOR_SAIDA", "saida"))


def fala(txt: str) -> None:
    print(f"  {txt}", flush=True)


def resumo_markdown(linhas: list[str]) -> None:
    arq = os.environ.get("GITHUB_STEP_SUMMARY")
    texto = "\n".join(linhas) + "\n"
    if arq:
        with open(arq, "a", encoding="utf-8") as f:
            f.write(texto)
    print(texto, flush=True)


def escolher_formato(duracao_estimada: float) -> str:
    """Disco do runner e curto: live longa desce em 720p."""
    if duracao_estimada and duracao_estimada > 9000:      # mais de 2h30
        return "best[height<=720]"
    return "best[height<=1080]"


def baixar(vod: str, destino: Path) -> Path:
    r = subprocess.run(["yt-dlp", "-J", "--no-warnings", "--no-playlist", vod],
                       capture_output=True, text=True, timeout=180)
    dur = 0.0
    try:
        dur = float(json.loads(r.stdout).get("duration") or 0)
    except Exception:
        pass
    fmt = escolher_formato(dur)
    fala(f"VOD de {dur/3600:.1f}h, baixando em {fmt}")
    twitch.baixar_vod(vod, destino, qualidade=fmt,
                      progresso=lambda f, t: None)
    return destino


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--vod", default="")
    p.add_argument("--arquivo", default="")
    p.add_argument("--quantos", type=int, default=6)
    p.add_argument("--perfil", default="gta6")
    p.add_argument("--alvo", type=float, default=150.0)
    p.add_argument("--minimo", type=float, default=45.0)
    p.add_argument("--maximo", type=float, default=180.0)
    p.add_argument("--fps-ocr", type=float, default=0.5,
                   help="quantas vezes por segundo ler o texto na tela")
    a = p.parse_args()

    plat = config.detectar()
    cfg = config.carregar()
    cfg.update({"perfil_hud": a.perfil, "duracao_alvo": a.alvo,
                "duracao_minima": a.minimo, "duracao_maxima": a.maximo,
                "chave_claude": os.environ.get("ANTHROPIC_API_KEY", ""),
                "usar_claude": bool(os.environ.get("ANTHROPIC_API_KEY"))})

    fala(plat.resumo()["descricao"])
    if not plat.ffmpeg:
        fala("sem ffmpeg, nao da pra seguir")
        return 1

    SAIDA.mkdir(parents=True, exist_ok=True)
    bruto = config.PASTA_BRUTO / "nuvem.mp4"

    t0 = time.time()
    if a.arquivo:
        fonte = Path(a.arquivo)
    elif a.vod:
        fonte = baixar(a.vod, bruto)
    else:
        fala("me da --vod ou --arquivo")
        return 2
    fala(f"video pronto em {time.time()-t0:.0f}s")

    inf = media.info(str(fonte), plat.ffprobe or "ffprobe")
    seg = max(1, int(np.ceil(inf.duracao)))
    fala(f"{inf.largura}x{inf.altura} a {inf.fps:.0f}fps, {inf.duracao/60:.0f} minutos")

    t0 = time.time()
    vis = s_vision.extrair(str(fonte), inf.duracao, 4.0, plat.ffmpeg)
    fala(f"imagem lida em {time.time()-t0:.0f}s, {len(vis['cortes'])} cortes de cena")

    aud = s_audio.extrair(media.audio_pcm(str(fonte), 16000, plat.ffmpeg), inf.duracao)
    fala("audio lido")

    perfil = s_gta.carregar_perfil(a.perfil, config.PASTA_PERFIS)
    leitor = s_gta.LeitorTexto(plat.ocr)
    t0 = time.time()
    jogo = s_gta.extrair(str(fonte), inf.duracao, perfil, leitor,
                         a.fps_ocr, plat.ffmpeg)
    fala(f"tela do jogo lida em {time.time()-t0:.0f}s, "
         f"{len(jogo['achados'])} eventos ({leitor.motor})")

    sinais = {**aud, "movimento": vis["movimento"], "flash": vis["flash"],
              "evento_jogo": jogo["evento_jogo"], "procurado": jogo["procurado"],
              "dano": jogo["dano"]}
    curva, norm = fuse.fundir(sinais, cfg["pesos"], seg)
    teto = float(curva.max()) or 1.0

    escolhidos = fuse.picos(curva, int(cfg["intervalo_minimo"]), a.quantos * 3)
    candidatos = []
    for pico in escolhidos:
        ini, fim = cortes.limites(pico, curva, vis["cortes"], inf.duracao,
                                  a.alvo, a.minimo, a.maximo)
        candidatos.append({"pico": pico, "inicio": ini, "fim": fim,
                           "nota": round(float(curva[pico]) / teto, 4),
                           "sinais": fuse.explicar(norm, pico)})
    candidatos = fuse.sem_sobreposicao(candidatos)
    candidatos = sorted(candidatos, key=lambda c: -c["nota"])[:a.quantos]
    candidatos = sorted(candidatos, key=lambda c: c["inicio"])
    fala(f"{len(candidatos)} momentos escolhidos")

    for i, c in enumerate(candidatos, 1):
        t = transcrever.transcrever(str(fonte), c["inicio"], c["fim"], cfg,
                                    plat.transcritor, plat.ffmpeg)
        c["transcricao"], c["palavras"] = t["texto"], t["palavras"]
        fala(f"transcrito {i} de {len(candidatos)}")

    textos = ia.avaliar(
        [{"indice": i, "nota": c["nota"], "sinais": c["sinais"],
          "duracao": round(c["fim"] - c["inicio"]),
          "transcricao": (c.get("transcricao") or "")[:700]}
         for i, c in enumerate(candidatos)],
        cfg["chave_claude"], cfg.get("modelo_claude", "claude-sonnet-4-5"))
    por_i = {int(t.get("indice", -1)): t for t in textos}
    for i, c in enumerate(candidatos):
        t = por_i.get(i, {})
        c["titulo"] = t.get("titulo", "") or f"momento {i+1}"
        c["legenda"] = t.get("legenda", "")
        c["hashtags"] = t.get("hashtags", [])

    linhas = ["## Clipes prontos", "",
              f"Fonte: {a.vod or a.arquivo}", "",
              "| # | quando | duracao | nota | titulo | por que |",
              "|---|--------|---------|------|--------|---------|"]

    for i, c in enumerate(candidatos, 1):
        nome = f"{i:02d}_{''.join(ch if ch.isalnum() else '_' for ch in c['titulo'])[:40]}.mp4"
        alvo = SAIDA / nome
        t0 = time.time()
        try:
            render.montar(str(fonte), c["inicio"], c["fim"], alvo,
                          cfg=cfg, plataforma=plat, perfil_hud=perfil,
                          perfil_acao=vis["perfil_acao"], perfil_brilho=vis["perfil_brilho"],
                          fps_perfil=vis["fps_perfil"], cortes_cena=vis["cortes"],
                          largura_fonte=inf.largura, altura_fonte=inf.altura,
                          palavras=c.get("palavras") or [], texto_titulo=c["titulo"])
            render.capa(str(fonte), (c["inicio"] + c["fim"]) / 2,
                        SAIDA / nome.replace(".mp4", ".jpg"), cfg, plat,
                        inf.largura, inf.altura, c["titulo"])
            fala(f"clipe {i} montado em {time.time()-t0:.0f}s")
        except Exception as e:
            fala(f"clipe {i} falhou: {e}")
            continue
        mm, ss = divmod(int(c["inicio"]), 60)
        linhas.append(
            f"| {i} | {mm//60}h{mm%60:02d}m{ss:02d}s | {int(c['fim']-c['inicio'])}s | "
            f"{int(c['nota']*100)} | {c['titulo']} | {', '.join(c['sinais']) or 'sinal fraco'} |")

    (SAIDA / "textos.json").write_text(json.dumps(
        [{"titulo": c["titulo"], "legenda": c["legenda"], "hashtags": c["hashtags"],
          "inicio": c["inicio"], "fim": c["fim"], "nota": c["nota"],
          "sinais": c["sinais"], "transcricao": c.get("transcricao", "")}
         for c in candidatos], ensure_ascii=False, indent=2), "utf-8")

    linhas += ["", "### Legendas pra copiar", ""]
    for i, c in enumerate(candidatos, 1):
        tags = " ".join("#" + h for h in c["hashtags"])
        linhas += [f"**{i}. {c['titulo']}**", "", f"{c['legenda']} {tags}", ""]

    resumo_markdown(linhas)

    if bruto.exists():
        bruto.unlink()
    fala(f"pronto: {len(list(SAIDA.glob('*.mp4')))} clipes em {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
