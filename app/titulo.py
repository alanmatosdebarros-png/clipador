"""Caixa de titulo desenhada como imagem: quebra certa, uma caixa so, sem invadir o jogo."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import PASTA_FONTES

CANDIDATAS = [
    "Montserrat-ExtraBold.ttf", "Montserrat-Black.ttf", "Montserrat-Bold.ttf",
]
SISTEMA = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def achar_fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for nome in CANDIDATAS:
        p = PASTA_FONTES / nome
        if p.exists():
            return ImageFont.truetype(str(p), tamanho)
    for p in SISTEMA:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, tamanho)
            except Exception:
                continue
    return ImageFont.load_default(tamanho)


def _quebrar(texto: str, fonte, largura_max: int, desenho) -> list[str]:
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if desenho.textlength(teste, font=fonte) <= largura_max or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def gerar(texto: str, destino: Path, largura: int = 1080, altura_max: int = 420,
          margem: int = 44, raio: int = 28, cor_caixa=(16, 16, 20, 232),
          cor_texto=(255, 255, 255, 255), faixa=(108, 78, 255, 255)) -> Path:
    """Uma caixa unica, do tamanho do texto, com faixa de cor na lateral."""
    texto = (texto or "").strip()
    if not texto:
        texto = "clipe"
    tamanho = 60
    img = Image.new("RGBA", (largura, altura_max), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    largura_texto = largura - margem * 2 - 56

    while tamanho > 26:
        fonte = achar_fonte(tamanho)
        linhas = _quebrar(texto, fonte, largura_texto, d)
        altura_linha = int(tamanho * 1.22)
        if len(linhas) <= 3 and len(linhas) * altura_linha + margem * 2 <= altura_max:
            break
        tamanho -= 4
    else:
        fonte = achar_fonte(tamanho)
        linhas = _quebrar(texto, fonte, largura_texto, d)
        altura_linha = int(tamanho * 1.22)
        linhas = linhas[:3]

    largura_caixa = int(max(d.textlength(l, font=fonte) for l in linhas)) + margem * 2 + 44
    largura_caixa = min(largura_caixa, largura - 32)
    altura_caixa = len(linhas) * altura_linha + margem

    img = Image.new("RGBA", (largura_caixa, altura_caixa), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, largura_caixa - 1, altura_caixa - 1], raio, fill=cor_caixa)
    d.rounded_rectangle([0, 0, 12, altura_caixa - 1], 6, fill=faixa)

    y = margem // 2
    for l in linhas:
        d.text((margem + 20, y), l, font=fonte, fill=cor_texto)
        y += altura_linha

    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino
