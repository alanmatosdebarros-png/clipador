"""Legenda em ASS com o tempo real de cada palavra, na zona segura do feed."""
from __future__ import annotations

import re
from pathlib import Path

PALAVRAO = re.compile(
    r"\b(caralh\w*|porra|merd\w*|fod[ae]\w*|put[ao]\w*|bucet\w*|cuz[aã]o|arrombad\w*|"
    r"desgra[cç]\w*|cacet\w*|viad\w*|pqp|krl|fdp|cu)\b", re.I)

CABECALHO = """[Script Info]
ScriptType: v4.00+
PlayResX: {larg}
PlayResY: {alt}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{fonte},{tam},&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{borda},{sombra},2,{marg},{marg},{margv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _t(s: float) -> str:
    s = max(0.0, s)
    h = int(s // 3600); m = int((s % 3600) // 60); seg = s % 60
    return f"{h:d}:{m:02d}:{seg:05.2f}"


def agrupar(palavras: list[dict], max_palavras: int = 4,
            max_duracao: float = 2.2, pausa: float = 0.6) -> list[list[dict]]:
    linhas: list[list[dict]] = []
    atual: list[dict] = []
    for w in palavras:
        if not w.get("p"):
            continue
        if atual:
            estoura = (len(atual) >= max_palavras
                       or w["fim"] - atual[0]["ini"] > max_duracao
                       or w["ini"] - atual[-1]["fim"] > pausa)
            if estoura:
                linhas.append(atual)
                atual = []
        atual.append(w)
    if atual:
        linhas.append(atual)
    return linhas


def gerar(palavras: list[dict], destino: Path, largura: int = 1080, altura: int = 1920,
          fonte: str = "Montserrat ExtraBold", topo_seguro: float = 0.20,
          base_segura: float = 0.72, bipar: bool = True,
          cor_destaque: str = "&H0036E8FF&") -> tuple[Path, list[tuple[float, float]]]:
    """Escreve o .ass e devolve os trechos de palavrao pra bipar no audio."""
    tam = int(altura * 0.042)
    margv = int(altura * (1 - base_segura))
    txt = CABECALHO.format(larg=largura, alt=altura, fonte=fonte, tam=tam,
                           borda=int(tam * 0.13), sombra=int(tam * 0.06),
                           marg=int(largura * 0.08), margv=margv)

    bipes: list[tuple[float, float]] = []
    eventos: list[str] = []

    for linha in agrupar(palavras):
        for alvo in linha:
            partes = []
            for w in linha:
                p = w["p"]
                if PALAVRAO.fullmatch(p.strip(".,!?;:")) :
                    if bipar:
                        bipes.append((w["ini"], w["fim"]))
                    p = p[0] + "*" * max(1, len(p) - 1)
                p = p.replace("{", "(").replace("}", ")")
                if w is alvo:
                    partes.append("{\\c" + cor_destaque + "\\fscx106\\fscy106}" + p + "{\\c&H00FFFFFF&\\fscx100\\fscy100}")
                else:
                    partes.append(p)
            ini, fim = alvo["ini"], max(alvo["fim"], alvo["ini"] + 0.08)
            eventos.append(f"Dialogue: 0,{_t(ini)},{_t(fim)},Base,,0,0,0,,{' '.join(partes)}")

    destino.write_text(txt + "\n".join(eventos) + "\n", "utf-8")
    # tira bipes repetidos
    unicos = sorted(set(bipes))
    return destino, unicos
