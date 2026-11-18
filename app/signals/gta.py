"""Camada de GTA: le o que acontece na tela do jogo.

Eventos por leitura de texto (WASTED, BUSTED, MISSAO CONCLUIDA, ELIMINADO),
estrelas de procurado, barra de vida caindo. A geometria vem do perfil de HUD,
que da pra calibrar na tela do app. A leitura de texto funciona sem calibrar.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np

from .. import media

LARG_OCR, ALT_OCR = 960, 540


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.upper())
                   if unicodedata.category(c) != "Mn")


class LeitorTexto:
    """Vision da Apple no Mac, tesseract fora dele, nada se nao tiver nenhum."""

    def __init__(self, motor: str):
        self.motor = motor
        self._vn = None
        if motor == "vision":
            try:
                import Vision  # type: ignore
                import Quartz  # type: ignore
                self._vn = (Vision, Quartz)
            except Exception:
                self.motor = "nenhum"
        elif motor == "tesseract":
            try:
                import pytesseract  # noqa: F401
            except Exception:
                self.motor = "nenhum"

    def ler(self, quadro: np.ndarray) -> str:
        if self.motor == "vision" and self._vn:
            return self._ler_vision(quadro)
        if self.motor == "tesseract":
            try:
                import pytesseract
                from PIL import Image
                return pytesseract.image_to_string(Image.fromarray(quadro), lang="por+eng")
            except Exception:
                return ""
        return ""

    def _ler_vision(self, quadro: np.ndarray) -> str:
        Vision, Quartz = self._vn  # type: ignore[misc]
        import Foundation  # type: ignore
        alt, larg, _ = quadro.shape
        dados = Foundation.NSData.dataWithBytes_length_(quadro.tobytes(), quadro.nbytes)
        prov = Quartz.CGDataProviderCreateWithCFData(dados)
        espaco = Quartz.CGColorSpaceCreateDeviceRGB()
        img = Quartz.CGImageCreate(larg, alt, 8, 24, larg * 3, espaco,
                                   Quartz.kCGBitmapByteOrderDefault, prov, None, False,
                                   Quartz.kCGRenderingIntentDefault)
        pedido = Vision.VNRecognizeTextRequest.alloc().init()
        pedido.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
        pedido.setUsesLanguageCorrection_(False)
        pedido.setRecognitionLanguages_(["pt-BR", "en-US"])
        tratador = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(img, None)
        ok = tratador.performRequests_error_([pedido], None)
        if not ok:
            return ""
        partes = []
        for obs in (pedido.results() or []):
            cands = obs.topCandidates_(1)
            if cands and len(cands):
                partes.append(str(cands[0].string()))
        return "\n".join(partes)


def carregar_perfil(nome: str, pasta: Path) -> dict:
    arq = pasta / f"{nome}.json"
    if not arq.exists():
        arq = pasta / "generico.json"
    return json.loads(arq.read_text("utf-8"))


def _recorte(q: np.ndarray, r: dict | None) -> np.ndarray | None:
    if not r:
        return None
    alt, larg, _ = q.shape
    x0, y0 = int(r["x"] * larg), int(r["y"] * alt)
    x1, y1 = int((r["x"] + r["w"]) * larg), int((r["y"] + r["h"]) * alt)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(larg, x1), min(alt, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return q[y0:y1, x0:x1]


def extrair(caminho: str, duracao: float, perfil: dict, leitor: LeitorTexto,
            fps_amostra: float = 1.0, ffmpeg: str = "ffmpeg", progresso=None) -> dict:
    segundos = max(1, int(np.ceil(duracao)))
    evento = np.zeros(segundos, np.float32)
    procurado = np.zeros(segundos, np.float32)
    dano = np.zeros(segundos, np.float32)
    achados: list[dict] = []

    regioes = perfil.get("regioes", {})
    eventos = {k: [_sem_acento(p) for p in v] for k, v in perfil.get("eventos", {}).items()}
    pesos = perfil.get("peso_evento", {})

    vida_ant = None
    estrela_ant = None
    i = 0
    total = int(duracao * fps_amostra) or 1

    for q in media.quadros(caminho, fps_amostra, LARG_OCR, ALT_OCR, ffmpeg=ffmpeg):
        t = i / fps_amostra
        s = min(segundos - 1, int(t))

        if leitor.motor != "nenhum":
            alvo = _recorte(q, regioes.get("banner")) if regioes.get("banner") else q
            texto = _sem_acento(leitor.ler(alvo if alvo is not None else q))
            if texto.strip():
                for tipo, palavras in eventos.items():
                    if any(p in texto for p in palavras):
                        peso = float(pesos.get(tipo, 0.7))
                        evento[s] = max(evento[s], peso)
                        achados.append({"t": round(t, 2), "tipo": tipo, "detalhe": texto[:80]})
                        break

        rp = _recorte(q, regioes.get("procurado"))
        if rp is not None:
            brilho = float(rp.mean())
            if estrela_ant is not None and brilho - estrela_ant > 12:
                procurado[s] = min(1.0, (brilho - estrela_ant) / 40.0)
            estrela_ant = brilho if estrela_ant is None else 0.7 * estrela_ant + 0.3 * brilho

        rv = _recorte(q, regioes.get("vida"))
        if rv is not None:
            # largura da parte clara da barra
            linha = rv.mean(axis=(0, 2))
            cheia = float((linha > linha.max() * 0.6).mean()) if linha.size else 0.0
            if vida_ant is not None and vida_ant - cheia > 0.08:
                dano[s] = min(1.0, (vida_ant - cheia) * 2.0)
            vida_ant = cheia

        i += 1
        if progresso and i % 120 == 0:
            progresso(min(0.99, i / total), "lendo a tela do jogo")

    return {"evento_jogo": evento, "procurado": procurado, "dano": dano, "achados": achados}
