"""Orquestra tudo: pega o video, acha os momentos, e depois monta so o que ele aprovar."""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from . import config, cortes, db, ia, media, render, transcrever, twitch
from .signals import audio as s_audio
from .signals import chat as s_chat
from .signals import fuse
from .signals import gta as s_gta
from .signals import vision as s_vision


class Trabalho:
    """Um processamento rodando, com recado e progresso pra tela."""

    def __init__(self):
        self.sessao_id: int | None = None
        self.estado = "parado"
        self.progresso = 0.0
        self.recado = ""
        self.erro = ""
        self._parar = threading.Event()
        self._t: threading.Thread | None = None
        self.gravador: twitch.GravadorAoVivo | None = None
        self.chat: twitch.ChatLogger | None = None

    def rodando(self) -> bool:
        return self._t is not None and self._t.is_alive()

    def aviso(self, fracao: float, texto: str) -> None:
        self.progresso = max(0.0, min(1.0, fracao))
        self.recado = texto
        if self.sessao_id:
            db.atualizar_sessao(self.sessao_id, progresso=self.progresso,
                                recado=texto, estado=self.estado)

    def parar(self) -> None:
        self._parar.set()
        if self.gravador:
            self.gravador.parar()
        if self.chat:
            self.chat.parar()

    # ---------------------------------------------------------------- VOD

    def comecar_vod(self, url: str, canal: str, cfg: dict, plat) -> int:
        sid = db.nova_sessao(canal, url, "vod", "depois")
        self.sessao_id, self.erro, self._parar = sid, "", threading.Event()
        self._t = threading.Thread(target=self._vod, args=(url, cfg, plat, sid), daemon=True)
        self._t.start()
        return sid

    def _vod(self, url: str, cfg: dict, plat, sid: int) -> None:
        try:
            self.estado = "baixando"
            destino = config.PASTA_BRUTO / f"sessao{sid}.mp4"
            self.aviso(0.02, "buscando o VOD na Twitch")
            twitch.baixar_vod(url, destino, progresso=lambda f, t: self.aviso(0.02 + f * 0.33, t))
            self._analisar(str(destino), sid, cfg, plat, offset=0.0, base_progresso=0.35)
            self.estado = "pronto"
            self.aviso(1.0, "momentos prontos, escolhe os que voce quer")
        except Exception as e:
            self.estado = "erro"
            self.erro = f"{e}\n{traceback.format_exc()[-800:]}"
            self.aviso(self.progresso, f"deu ruim: {e}")

    # ------------------------------------------------------------ ao vivo

    def comecar_ao_vivo(self, canal: str, cfg: dict, plat) -> int:
        sid = db.nova_sessao(canal, f"live de {canal}", "live", "ao_vivo")
        self.sessao_id, self.erro, self._parar = sid, "", threading.Event()
        self._t = threading.Thread(target=self._ao_vivo, args=(canal, cfg, plat, sid), daemon=True)
        self._t.start()
        return sid

    def _ao_vivo(self, canal: str, cfg: dict, plat, sid: int) -> None:
        try:
            pasta = config.PASTA_BRUTO / f"live{sid}"
            self.gravador = twitch.GravadorAoVivo(canal, pasta, 300, plat.ffmpeg or "ffmpeg")
            self.chat = twitch.ChatLogger(canal, config.PASTA_DADOS / f"chat{sid}.jsonl")
            self.estado = "ao vivo"
            self.aviso(0.01, "entrando no chat e na transmissao")
            self.chat.comecar()
            self.gravador.comecar()
            db.atualizar_sessao(sid, caminho_video=str(pasta))

            feitos: set[str] = set()
            while not self._parar.is_set():
                pedacos = self.gravador.pedacos_prontos()
                # so analisa um pedaco quando o seguinte ja fechou (contexto dos dois lados)
                for i in range(len(pedacos) - 1):
                    chave = pedacos[i]["arquivo"]
                    if chave in feitos:
                        continue
                    feitos.add(chave)
                    par = config.PASTA_BRUTO / f"live{sid}" / f"par{i}.txt"
                    par.write_text("".join(
                        f"file '{p['arquivo']}'\n" for p in pedacos[i:i + 2]), "utf-8")
                    self.aviso(0.5, f"analisando os minutos {int(pedacos[i]['inicio']//60)} em diante")
                    self._analisar(str(par), sid, cfg, plat,
                                   offset=pedacos[i]["inicio"], concat=True,
                                   so_ate=pedacos[i]["fim"] - pedacos[i]["inicio"],
                                   base_progresso=0.5, acumular=True)
                time.sleep(15)

            self.gravador.parar()
            self.chat.parar()
            self.estado = "pronto"
            self.aviso(1.0, "live encerrada, momentos prontos")
        except Exception as e:
            self.estado = "erro"
            self.erro = f"{e}\n{traceback.format_exc()[-800:]}"
            self.aviso(self.progresso, f"deu ruim: {e}")

    # ------------------------------------------------------------ analise

    def _analisar(self, caminho: str, sid: int, cfg: dict, plat,
                  offset: float = 0.0, concat: bool = False,
                  so_ate: float | None = None, base_progresso: float = 0.0,
                  acumular: bool = False) -> None:
        self.estado = "analisando"
        entrada = ["-f", "concat", "-safe", "0", "-i", caminho] if concat else ["-i", caminho]
        fonte = caminho
        if concat:
            # junta num arquivo so pra poder cortar depois com precisao
            juntado = config.PASTA_BRUTO / f"live{sid}" / (Path(caminho).stem + ".mp4")
            subprocess.run([plat.ffmpeg or "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-fflags", "+genpts", "-f", "concat", "-safe", "0", "-i", caminho,
                            "-c", "copy", "-avoid_negative_ts", "make_zero",
                            "-muxpreload", "0", "-muxdelay", "0",
                            str(juntado)], check=True, capture_output=True)
            fonte = str(juntado)

        inf = media.info(fonte, plat.ffprobe or "ffprobe")
        db.atualizar_sessao(sid, caminho_video=fonte, duracao=inf.duracao, fps=inf.fps,
                            largura=inf.largura, altura=inf.altura)
        seg = max(1, int(np.ceil(inf.duracao)))

        self.aviso(base_progresso + 0.05, "lendo a imagem (corte de cena, movimento, clarao)")
        vis = s_vision.extrair(fonte, inf.duracao, 4.0, plat.ffmpeg or "ffmpeg",
                               progresso=lambda f, t: self.aviso(base_progresso + 0.05 + f * 0.18, t))

        self.aviso(base_progresso + 0.24, "ouvindo o audio")
        aud = s_audio.extrair(media.audio_pcm(fonte, 16000, plat.ffmpeg or "ffmpeg"), inf.duracao)

        perfil = s_gta.carregar_perfil(cfg.get("perfil_hud", "generico"), config.PASTA_PERFIS)
        leitor = s_gta.LeitorTexto(plat.ocr)
        jogo = {"evento_jogo": np.zeros(seg, np.float32),
                "procurado": np.zeros(seg, np.float32),
                "dano": np.zeros(seg, np.float32), "achados": []}
        if leitor.motor != "nenhum" or perfil.get("regioes", {}).get("vida"):
            self.aviso(base_progresso + 0.28, "lendo a tela do jogo")
            jogo = s_gta.extrair(fonte, inf.duracao, perfil, leitor, 1.0, plat.ffmpeg or "ffmpeg",
                                 progresso=lambda f, t: self.aviso(base_progresso + 0.28 + f * 0.14, t))

        cha = {}
        arq_chat = config.PASTA_DADOS / f"chat{sid}.jsonl"
        if arq_chat.exists():
            inicio_epoch = (self.chat.inicio_epoch if self.chat else 0.0) + offset
            cha = s_chat.extrair(s_chat.carregar(arq_chat), inicio_epoch, inf.duracao)

        sinais = {**aud, **cha,
                  "movimento": vis["movimento"], "flash": vis["flash"],
                  "evento_jogo": jogo["evento_jogo"], "procurado": jogo["procurado"],
                  "dano": jogo["dano"]}
        curva, norm = fuse.fundir(sinais, cfg["pesos"], seg)

        np.savez_compressed(config.PASTA_DADOS / f"sinais{sid}_{int(offset)}.npz",
                            perfil_acao=vis["perfil_acao"], perfil_brilho=vis["perfil_brilho"],
                            curva=curva, fps_perfil=np.float32(vis["fps_perfil"]),
                            cortes=np.array(vis["cortes"], np.float32))

        for a in jogo["achados"]:
            db.ex("INSERT INTO evento (sessao_id,t,tipo,detalhe) VALUES (?,?,?,?)",
                  (sid, a["t"] + offset, a["tipo"], a["detalhe"]))

        self.aviso(base_progresso + 0.44, "escolhendo os momentos")
        limite = int(so_ate) if so_ate else seg
        # no modo ao vivo so valem picos da primeira metade da janela, mas o corte
        # ainda enxerga o que vem depois. Zera o resto antes de escolher, senao um
        # pico de fora derruba um bom pico de dentro.
        curva_escolha = curva.copy()
        if limite < seg:
            curva_escolha[limite:] = 0.0
        escolhidos = fuse.picos(curva_escolha, int(cfg["intervalo_minimo"]),
                                int(cfg["maximo_candidatos"]))

        teto = float(curva.max()) or 1.0
        candidatos = []
        for p in escolhidos:
            ini, fim = cortes.limites(p, curva, vis["cortes"], inf.duracao,
                                      float(cfg["duracao_alvo"]), float(cfg["duracao_minima"]),
                                      float(cfg["duracao_maxima"]))
            candidatos.append({"pico": p, "inicio": ini, "fim": fim,
                               "nota": round(float(curva[p]) / teto, 4),
                               "sinais": fuse.explicar(norm, p),
                               "fonte": fonte, "offset": offset})
        candidatos = fuse.sem_sobreposicao(candidatos)

        self.aviso(base_progresso + 0.5, f"transcrevendo {len(candidatos)} trechos")
        for i, c in enumerate(candidatos):
            if self._parar.is_set():
                break
            t = transcrever.transcrever(fonte, c["inicio"], c["fim"], cfg,
                                        plat.transcritor, plat.ffmpeg or "ffmpeg")
            c["transcricao"] = t["texto"]
            c["palavras"] = t["palavras"]
            self.aviso(base_progresso + 0.5 + (i + 1) / max(1, len(candidatos)) * 0.3,
                       f"transcrevendo {i+1} de {len(candidatos)}")

        self.aviso(base_progresso + 0.84, "pedindo titulo e legenda")
        resumo = [{"indice": i, "nota": c["nota"], "sinais": c["sinais"],
                   "duracao": round(c["fim"] - c["inicio"]),
                   "transcricao": (c.get("transcricao") or "")[:700]}
                  for i, c in enumerate(candidatos)]
        textos = ia.avaliar(resumo, cfg.get("chave_claude", "") if cfg.get("usar_claude") else "",
                            cfg.get("modelo_claude", "claude-sonnet-4-5"))
        por_indice = {int(t.get("indice", -1)): t for t in textos}
        for i, c in enumerate(candidatos):
            t = por_indice.get(i, {})
            c["titulo"] = t.get("titulo", "")
            c["legenda"] = t.get("legenda", "")
            c["hashtags"] = t.get("hashtags", [])
            if t.get("vale") is not None:
                c["nota"] = round(float(t["vale"]) / 100.0, 4)
            c["resumo"] = json.dumps({"fonte": fonte, "offset": offset,
                                      "palavras": c.get("palavras", [])}, ensure_ascii=False)

        if acumular:
            # evita repetir um momento que a janela anterior ja pegou
            ja = db.todos("SELECT inicio,fim,pico FROM candidato WHERE sessao_id=?", (sid,))
            def repetido(c):
                a, b = c["inicio"] + offset, c["fim"] + offset
                for v in ja:
                    ini = max(a, float(v["inicio"]))
                    fim = min(b, float(v["fim"]))
                    comum = max(0.0, fim - ini)
                    menor = min(b - a, float(v["fim"]) - float(v["inicio"])) or 1.0
                    if comum / menor > 0.35:
                        return True
                return False
            candidatos = [c for c in candidatos if not repetido(c)]
            for c in candidatos:
                db.ex("INSERT INTO candidato (sessao_id,pico,inicio,fim,nota,sinais,resumo,"
                      "transcricao,titulo,legenda,hashtags,estado,criado_em)"
                      " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (sid, c["pico"] + offset, c["inicio"], c["fim"], c["nota"],
                       json.dumps(c["sinais"], ensure_ascii=False), c["resumo"],
                       c.get("transcricao", ""), c["titulo"], c["legenda"],
                       json.dumps(c["hashtags"], ensure_ascii=False), "candidato", time.time()))
        else:
            db.salvar_candidatos(sid, candidatos)


def montar_clipe(candidato_id: int, cfg: dict, plat) -> Path:
    """Monta o MP4 de um candidato aprovado."""
    c = db.um("SELECT * FROM candidato WHERE id=?", (candidato_id,))
    if not c:
        raise RuntimeError("candidato nao existe")
    s = db.um("SELECT * FROM sessao WHERE id=?", (c["sessao_id"],))
    extra = json.loads(c.get("resumo") or "{}")
    fonte = extra.get("fonte") or (s or {}).get("caminho_video")
    offset = float(extra.get("offset") or 0.0)
    if not fonte or not Path(fonte).exists():
        raise RuntimeError("o video bruto desse momento ja foi apagado")

    npz = config.PASTA_DADOS / f"sinais{c['sessao_id']}_{int(offset)}.npz"
    if npz.exists():
        d = np.load(npz)
        perfil_acao, perfil_brilho = d["perfil_acao"], d["perfil_brilho"]
        fps_perfil = float(d["fps_perfil"])
        cortes_cena = [float(x) for x in d["cortes"]]
    else:
        perfil_acao = perfil_brilho = np.zeros((1, 32), np.float32)
        fps_perfil, cortes_cena = 4.0, []

    inf = media.info(fonte, plat.ffprobe or "ffprobe")
    perfil = s_gta.carregar_perfil(cfg.get("perfil_hud", "generico"), config.PASTA_PERFIS)
    destino = config.PASTA_CLIPES / f"clipe{candidato_id}.mp4"

    render.montar(fonte, float(c["inicio"]), float(c["fim"]), destino,
                  cfg=cfg, plataforma=plat, perfil_hud=perfil,
                  perfil_acao=perfil_acao, perfil_brilho=perfil_brilho,
                  fps_perfil=fps_perfil, cortes_cena=cortes_cena,
                  largura_fonte=inf.largura, altura_fonte=inf.altura,
                  palavras=extra.get("palavras") or [],
                  texto_titulo=c.get("titulo") or "")

    capa = ""
    if cfg.get("capa_automatica", True):
        p = config.PASTA_CAPAS / f"capa{candidato_id}.jpg"
        render.capa(fonte, (float(c["inicio"]) + float(c["fim"])) / 2, p, cfg, plat,
                    inf.largura, inf.altura, c.get("titulo") or "")
        capa = str(p)

    db.ex("UPDATE candidato SET estado='pronto', arquivo=?, capa=? WHERE id=?",
          (str(destino), capa, candidato_id))
    return destino


def limpar_bruto(sessao_id: int) -> int:
    """Apaga o video bruto da sessao. Os clipes aprovados ficam."""
    s = db.um("SELECT * FROM sessao WHERE id=?", (sessao_id,))
    if not s:
        return 0
    liberado = 0
    alvos = [Path(s["caminho_video"] or "")] if s.get("caminho_video") else []
    alvos.append(config.PASTA_BRUTO / f"live{sessao_id}")
    alvos.append(config.PASTA_BRUTO / f"sessao{sessao_id}.mp4")
    for a in alvos:
        if a.is_dir():
            liberado += sum(f.stat().st_size for f in a.rglob("*") if f.is_file())
            shutil.rmtree(a, ignore_errors=True)
        elif a.is_file():
            liberado += a.stat().st_size
            a.unlink(missing_ok=True)
    return liberado
