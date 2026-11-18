"""Configuracao e deteccao de plataforma do Clipador."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path

BASE = Path(os.environ.get("CLIPADOR_HOME", Path.home() / "Clipador"))
PASTA_BRUTO = BASE / "bruto"        # pedacos da live e VODs baixados (apagados depois)
PASTA_CLIPES = BASE / "clipes"      # so o que ele aprovou fica aqui
PASTA_CAPAS = BASE / "capas"
PASTA_DADOS = BASE / "dados"        # chat, sinais, banco
PASTA_PERFIS = BASE / "perfis"      # perfis de HUD por jogo
PASTA_FONTES = BASE / "fontes"

for _p in (PASTA_BRUTO, PASTA_CLIPES, PASTA_CAPAS, PASTA_DADOS, PASTA_PERFIS, PASTA_FONTES):
    _p.mkdir(parents=True, exist_ok=True)

ARQ_CONFIG = PASTA_DADOS / "config.json"
BANCO = PASTA_DADOS / "clipador.db"


def _tem(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


@dataclass(frozen=True)
class Plataforma:
    """O que esta maquina consegue fazer de verdade."""
    sistema: str
    apple_silicon: bool
    ffmpeg: str
    ffprobe: str
    encoder_video: str
    encoder_hardware: bool
    transcritor: str      # mlx | faster | nenhum
    ocr: str              # vision | tesseract | nenhum
    saliencia: str        # vision | opencv | movimento
    nucleos: int

    def resumo(self) -> dict:
        d = asdict(self)
        d["descricao"] = (
            f"{self.sistema}, {self.nucleos} nucleos, video por "
            f"{'hardware' if self.encoder_hardware else 'software'} ({self.encoder_video}), "
            f"transcricao: {self.transcritor}, leitura de tela: {self.ocr}"
        )
        return d


EXTRAS_BIN = [
    Path.home() / "Clipador" / "venv" / "bin",
    Path("/opt/homebrew/bin"),
    Path("/usr/local/bin"),
    Path("/opt/local/bin"),
]


def _achar_ffmpeg() -> tuple[str, str]:
    """Procura no PATH, nas pastas comuns do Mac e, por ultimo, no static-ffmpeg."""
    f = shutil.which("ffmpeg") or ""
    p = shutil.which("ffprobe") or ""
    if f and p:
        return f, p
    for pasta in EXTRAS_BIN:
        if not f and (pasta / "ffmpeg").exists():
            f = str(pasta / "ffmpeg")
        if not p and (pasta / "ffprobe").exists():
            p = str(pasta / "ffprobe")
    if f and p:
        return f, p
    try:
        from static_ffmpeg import run as _run  # type: ignore
        a, b = _run.get_or_fetch_platform_executables_else_raise()
        return f or str(a), p or str(b)
    except Exception:
        return f, p


def _encoder(ffmpeg: str) -> tuple[str, bool]:
    if not ffmpeg:
        return "libx264", False
    try:
        saida = subprocess.run([ffmpeg, "-hide_banner", "-encoders"],
                               capture_output=True, text=True, timeout=20).stdout
    except Exception:
        return "libx264", False
    if "h264_videotoolbox" in saida:
        return "h264_videotoolbox", True
    return "libx264", False


def detectar() -> Plataforma:
    sistema = platform.system()
    maquina = platform.machine()
    apple = sistema == "Darwin" and maquina == "arm64"
    ffmpeg, ffprobe = _achar_ffmpeg()
    enc, hw = _encoder(ffmpeg)

    if apple and _tem("mlx_whisper"):
        transcritor = "mlx"
    elif _tem("faster_whisper"):
        transcritor = "faster"
    else:
        transcritor = "nenhum"

    if apple and _tem("Vision"):
        ocr, sal = "vision", "vision"
    else:
        ocr = "tesseract" if shutil.which("tesseract") else "nenhum"
        sal = "opencv" if _tem("cv2") else "movimento"

    return Plataforma(
        sistema=f"{sistema} {maquina}",
        apple_silicon=apple,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        encoder_video=enc,
        encoder_hardware=hw,
        transcritor=transcritor,
        ocr=ocr,
        saliencia=sal,
        nucleos=os.cpu_count() or 4,
    )


PADRAO = {
    "canal_twitch": "",
    "modo": "depois",                 # depois | ao_vivo
    "jogo": "gta",
    "perfil_hud": "gta6",

    "duracao_alvo": 150,              # 2min30
    "duracao_minima": 45,
    "duracao_maxima": 180,
    "intervalo_minimo": 150,           # distancia minima entre dois clipes
    "maximo_candidatos": 25,

    "pesos": {
        "chat": 1.0,
        "audio": 0.8,
        "voz": 0.7,
        "movimento": 0.5,
        "flash": 0.5,
        "evento_jogo": 1.2,
        "marcador": 2.0,
    },

    "fps_saida": 60,
    "largura_saida": 1080,
    "altura_saida": 1920,
    "volume_alvo_lufs": -14.0,
    "pico_maximo_dbtp": -1.0,

    "legenda": True,
    "legenda_topo_seguro": 0.20,      # fracao da altura: nada de legenda acima disso
    "legenda_base_segura": 0.72,      # nem abaixo disso (area dos botoes do TikTok)
    "bipar_palavrao": True,
    "inserto_minimapa": True,
    "capa_automatica": True,

    "transcricao_completa": False,    # False = so em volta dos candidatos (bem mais rapido)
    "modelo_transcricao": "mlx-community/whisper-small-mlx",
    "modelo_transcricao_fallback": "small",
    "idioma": "pt",

    "chave_claude": "",
    "modelo_claude": "claude-sonnet-4-5",
    "usar_claude": True,

    "apagar_bruto_depois": True,
    "limite_disco_gb": 60,

    "tema": "escuro",
}


def carregar() -> dict:
    cfg = json.loads(json.dumps(PADRAO))
    if ARQ_CONFIG.exists():
        try:
            salvo = json.loads(ARQ_CONFIG.read_text("utf-8"))
            for k, v in salvo.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def salvar(cfg: dict) -> dict:
    ARQ_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), "utf-8")
    return cfg
