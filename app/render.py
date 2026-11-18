"""Monta o clipe: 9:16, 60fps, volume equalizado de verdade, legenda e titulo."""
from __future__ import annotations

import shlex
import subprocess
import tempfile
from pathlib import Path

from . import legendas, media, reenquadre, titulo


def _esc(caminho: str | Path) -> str:
    """Escapa caminho pra dentro de filtro do ffmpeg."""
    s = str(caminho)
    return s.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def montar(
    fonte: str,
    inicio: float,
    fim: float,
    destino: Path,
    *,
    cfg: dict,
    plataforma,
    perfil_hud: dict,
    perfil_acao,
    perfil_brilho,
    fps_perfil: float,
    cortes_cena: list[float],
    largura_fonte: int,
    altura_fonte: int,
    palavras: list[dict] | None = None,
    texto_titulo: str = "",
    pasta_trabalho: Path | None = None,
) -> Path:
    ffmpeg = plataforma.ffmpeg or "ffmpeg"
    larg_saida = int(cfg.get("largura_saida", 1080))
    alt_saida = int(cfg.get("altura_saida", 1920))
    fps = int(cfg.get("fps_saida", 60))
    dur = max(0.5, fim - inicio)

    tmpdir = pasta_trabalho or Path(tempfile.mkdtemp(prefix="clipe_"))
    tmpdir.mkdir(parents=True, exist_ok=True)

    # 1. caminho do corte que segue a acao
    larg_corte = int(round(altura_fonte * larg_saida / alt_saida)) // 2 * 2
    larg_corte = min(larg_corte, largura_fonte)
    pontos = reenquadre.caminho(perfil_acao, perfil_brilho, fps_perfil, inicio, fim,
                                largura_fonte, larg_corte, cortes_cena)
    arq_cmd = reenquadre.escrever_sendcmd(pontos, tmpdir / "corte.cmd")

    cadeia = [
        f"fps={fps}",
        f"sendcmd=f='{_esc(arq_cmd)}'",
        f"crop={larg_corte}:{altura_fonte}:{pontos[0][1]}:0",
        f"scale={larg_saida}:{alt_saida}:flags=bicubic",
        "setsar=1",
    ]
    filtros = [f"[0:v]{','.join(cadeia)}[base]"]
    rotulo = "base"
    entradas_extra: list[str] = []
    n_entrada = 1

    regioes = perfil_hud.get("regioes", {})

    # 2. facecam, se o perfil tiver uma (camera do PS5 fica sempre no mesmo lugar)
    face = reenquadre.regiao_px(regioes.get("facecam"), largura_fonte, altura_fonte)
    if face:
        x, y, w, h = face
        lf = int(larg_saida * 0.42)
        filtros.append(f"[0:v]crop={w}:{h}:{x}:{y},scale={lf}:-2[face]")
        filtros.append(f"[{rotulo}][face]overlay=x={int(larg_saida*0.03)}:"
                       f"y={int(alt_saida*0.055)}[comface]")
        rotulo = "comface"

    # 3. inserto do minimapa, que o corte vertical deixaria de fora
    mini = reenquadre.regiao_px(regioes.get("minimapa"), largura_fonte, altura_fonte)
    if mini and cfg.get("inserto_minimapa", True):
        x, y, w, h = mini
        lm = int(larg_saida * 0.30)
        filtros.append(f"[0:v]crop={w}:{h}:{x}:{y},scale={lm}:-2[mini]")
        # canto de cima a direita: nao briga com a legenda nem com os botoes do TikTok
        filtros.append(f"[{rotulo}][mini]overlay=x=W-w-{int(larg_saida*0.035)}:"
                       f"y={int(alt_saida*0.045)}:format=auto[commini]")
        rotulo = "commini"

    # 4. legenda com o tempo real de cada palavra
    bipes: list[tuple[float, float]] = []
    if cfg.get("legenda", True) and palavras:
        ass, bipes = legendas.gerar(
            palavras, tmpdir / "legenda.ass", larg_saida, alt_saida,
            topo_seguro=float(cfg.get("legenda_topo_seguro", 0.20)),
            base_segura=float(cfg.get("legenda_base_segura", 0.72)),
            bipar=bool(cfg.get("bipar_palavrao", True)),
        )
        filtros.append(f"[{rotulo}]ass='{_esc(ass)}'[comleg]")
        rotulo = "comleg"

    # 5. caixa de titulo, uma so, com quebra certa
    if texto_titulo.strip():
        png = titulo.gerar(texto_titulo, tmpdir / "titulo.png", larg_saida)
        entradas_extra += ["-i", str(png)]
        filtros.append(f"[{rotulo}][{n_entrada}:v]overlay=x={int(larg_saida*0.04)}:"
                       f"y={int(alt_saida*0.215)}[comtit]")
        rotulo = "comtit"
        n_entrada += 1

    filtros.append(f"[{rotulo}]format=yuv420p[vfinal]")

    # 6. audio: bipe no palavrao com o tempo certo, depois loudnorm de duas passadas
    cadeia_audio = []
    for (a, b) in bipes:
        cadeia_audio.append(f"volume=enable='between(t,{a:.2f},{b:.2f})':volume=0")
    medido = media.medir_loudness(fonte, inicio, fim, ffmpeg)
    alvo_i = float(cfg.get("volume_alvo_lufs", -14.0))
    alvo_tp = float(cfg.get("pico_maximo_dbtp", -1.0))
    if medido.get("input_i"):
        cadeia_audio.append(
            f"loudnorm=I={alvo_i}:TP={alvo_tp}:LRA=11:"
            f"measured_I={medido['input_i']}:measured_TP={medido['input_tp']}:"
            f"measured_LRA={medido['input_lra']}:measured_thresh={medido['input_thresh']}:"
            f"offset={medido.get('target_offset','0')}:linear=true:print_format=summary"
        )
    else:
        cadeia_audio.append(f"loudnorm=I={alvo_i}:TP={alvo_tp}:LRA=11")
    cadeia_audio.append("aresample=48000")
    filtros.append(f"[0:a]{','.join(cadeia_audio)}[afinal]")

    if plataforma.encoder_hardware:
        video_args = ["-c:v", "h264_videotoolbox", "-b:v", "9M", "-maxrate", "12M",
                      "-profile:v", "high", "-realtime", "0"]
    else:
        video_args = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]

    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{inicio:.3f}", "-i", str(fonte), *entradas_extra,
           "-t", f"{dur:.3f}",
           "-filter_complex", ";".join(filtros),
           "-map", "[vfinal]", "-map", "[afinal]",
           *video_args,
           "-r", str(fps),
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
           "-movflags", "+faststart", str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not destino.exists():
        raise RuntimeError(f"ffmpeg falhou: {r.stderr.strip()[-700:]}\ncmd: {shlex.join(cmd)}")
    return destino


def capa(fonte: str, t: float, destino: Path, cfg: dict, plataforma,
         largura_fonte: int, altura_fonte: int, texto: str = "") -> Path:
    ffmpeg = plataforma.ffmpeg or "ffmpeg"
    larg, alt = int(cfg.get("largura_saida", 1080)), int(cfg.get("altura_saida", 1920))
    larg_corte = int(round(altura_fonte * larg / alt)) // 2 * 2
    x = max(0, (largura_fonte - larg_corte) // 2)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
           "-ss", f"{t:.3f}", "-i", str(fonte), "-frames:v", "1",
           "-vf", f"crop={larg_corte}:{altura_fonte}:{x}:0,scale={larg}:{alt}",
           str(destino)]
    subprocess.run(cmd, capture_output=True, check=False)
    if texto.strip() and destino.exists():
        from PIL import Image
        base = Image.open(destino).convert("RGBA")
        png = titulo.gerar(texto, destino.with_suffix(".tit.png"), larg)
        cx = Image.open(png).convert("RGBA")
        base.alpha_composite(cx, (int(larg * 0.04), int(alt * 0.215)))
        base.convert("RGB").save(destino)
    return destino
