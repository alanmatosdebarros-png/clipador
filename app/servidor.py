"""Servidor local do Clipador. So biblioteca padrao, nada de framework."""
from __future__ import annotations

import json
import mimetypes
import re
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, db, pipeline, twitch
from .signals import gta as s_gta

RAIZ_UI = Path(__file__).resolve().parent.parent / "ui"
PLATAFORMA = config.detectar()
TRABALHO = pipeline.Trabalho()
TRAVA = threading.Lock()


def _perfis() -> list[dict]:
    saida = []
    for p in sorted(config.PASTA_PERFIS.glob("*.json")):
        try:
            d = json.loads(p.read_text("utf-8"))
            saida.append({"id": p.stem, "nome": d.get("nome", p.stem),
                          "calibrado": bool(d.get("calibrado"))})
        except Exception:
            continue
    return saida


def _sessoes() -> list[dict]:
    return db.todos("SELECT id,canal,titulo,origem,modo,duracao,criada_em,estado,progresso,recado"
                    " FROM sessao ORDER BY id DESC LIMIT 20")


def _candidatos(sid: int) -> list[dict]:
    itens = db.todos("SELECT * FROM candidato WHERE sessao_id=? ORDER BY nota DESC", (sid,))
    for c in itens:
        c["sinais"] = json.loads(c.get("sinais") or "{}")
        c["hashtags"] = json.loads(c.get("hashtags") or "[]")
        c.pop("resumo", None)
        c["duracao"] = round(float(c["fim"]) - float(c["inicio"]), 1)
    return itens


class Mao(BaseHTTPRequestHandler):
    server_version = "Clipador"

    def log_message(self, *a):  # silencio no terminal
        pass

    # ------------------------------------------------------------- base

    def _json(self, dados, codigo: int = 200) -> None:
        corpo = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _arquivo(self, caminho: Path, baixar: bool = False) -> None:
        if not caminho.exists() or not caminho.is_file():
            return self._json({"erro": "nao achei o arquivo"}, 404)
        tipo = mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
        tamanho = caminho.stat().st_size
        faixa = self.headers.get("Range")
        inicio, fim = 0, tamanho - 1
        codigo = 200
        if faixa:
            m = re.match(r"bytes=(\d*)-(\d*)", faixa)
            if m:
                if m.group(1):
                    inicio = int(m.group(1))
                if m.group(2):
                    fim = min(int(m.group(2)), tamanho - 1)
                codigo = 206
        n = fim - inicio + 1
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(n))
        if codigo == 206:
            self.send_header("Content-Range", f"bytes {inicio}-{fim}/{tamanho}")
        if baixar:
            self.send_header("Content-Disposition", f'attachment; filename="{caminho.name}"')
        self.end_headers()
        with caminho.open("rb") as f:
            f.seek(inicio)
            restante = n
            while restante > 0:
                pedaco = f.read(min(262144, restante))
                if not pedaco:
                    break
                try:
                    self.wfile.write(pedaco)
                except (BrokenPipeError, ConnectionResetError):
                    return
                restante -= len(pedaco)

    # -------------------------------------------------------------- GET

    def do_GET(self) -> None:
        u = urllib.parse.urlparse(self.path)
        rota, q = u.path, urllib.parse.parse_qs(u.query)

        if rota in ("/", "/index.html"):
            return self._arquivo(RAIZ_UI / "index.html")
        if rota.startswith("/ui/"):
            alvo = (RAIZ_UI / rota[4:]).resolve()
            if RAIZ_UI.resolve() in alvo.parents:
                return self._arquivo(alvo)
            return self._json({"erro": "fora da pasta"}, 403)

        if rota == "/api/estado":
            return self._json({
                "plataforma": PLATAFORMA.resumo(),
                "config": config.carregar(),
                "perfis": _perfis(),
                "sessoes": _sessoes(),
                "trabalho": {"estado": TRABALHO.estado, "progresso": TRABALHO.progresso,
                             "recado": TRABALHO.recado, "sessao_id": TRABALHO.sessao_id,
                             "rodando": TRABALHO.rodando(), "erro": TRABALHO.erro},
                "pastas": {"clipes": str(config.PASTA_CLIPES), "base": str(config.BASE)},
            })

        m = re.match(r"^/api/sessao/(\d+)/candidatos$", rota)
        if m:
            return self._json({"candidatos": _candidatos(int(m.group(1)))})

        if rota == "/api/fila":
            itens = db.todos("SELECT * FROM candidato WHERE estado IN ('pronto','agendado')"
                             " ORDER BY agendado_para IS NULL, agendado_para")
            for c in itens:
                c["hashtags"] = json.loads(c.get("hashtags") or "[]")
                c.pop("resumo", None)
            return self._json({"fila": itens})

        if rota == "/arquivo":
            caminho = Path((q.get("c") or [""])[0]).resolve()
            permitido = any(str(caminho).startswith(str(p.resolve()))
                            for p in (config.PASTA_CLIPES, config.PASTA_CAPAS, config.PASTA_BRUTO))
            if not permitido:
                return self._json({"erro": "caminho nao permitido"}, 403)
            return self._arquivo(caminho, baixar=bool(q.get("baixar")))

        return self._json({"erro": "rota desconhecida"}, 404)

    # ------------------------------------------------------------- POST

    def do_POST(self) -> None:
        rota = urllib.parse.urlparse(self.path).path
        corpo = self._corpo()
        cfg = config.carregar()

        if rota == "/api/config":
            for k, v in corpo.items():
                if k in cfg:
                    if isinstance(cfg[k], dict) and isinstance(v, dict):
                        cfg[k].update(v)
                    else:
                        cfg[k] = v
            return self._json({"config": config.salvar(cfg)})

        if rota == "/api/canal/checar":
            canal = (corpo.get("canal") or cfg.get("canal_twitch") or "").strip().lstrip("@")
            if not canal:
                return self._json({"erro": "me diz o nome do canal"}, 400)
            estado = twitch.esta_ao_vivo(canal)
            estado["vods"] = twitch.listar_vods(canal, 10)
            return self._json(estado)

        if rota == "/api/vod/analisar":
            with TRAVA:
                if TRABALHO.rodando():
                    return self._json({"erro": "ja tem coisa rodando"}, 409)
                url = (corpo.get("url") or "").strip()
                if not url:
                    return self._json({"erro": "faltou o link do VOD"}, 400)
                sid = TRABALHO.comecar_vod(url, cfg.get("canal_twitch", ""), cfg, PLATAFORMA)
            return self._json({"sessao_id": sid})

        if rota == "/api/live/comecar":
            with TRAVA:
                if TRABALHO.rodando():
                    return self._json({"erro": "ja tem coisa rodando"}, 409)
                canal = (corpo.get("canal") or cfg.get("canal_twitch") or "").strip().lstrip("@")
                if not canal:
                    return self._json({"erro": "me diz o nome do canal"}, 400)
                sid = TRABALHO.comecar_ao_vivo(canal, cfg, PLATAFORMA)
            return self._json({"sessao_id": sid})

        if rota == "/api/live/parar":
            TRABALHO.parar()
            return self._json({"ok": True})

        m = re.match(r"^/api/candidato/(\d+)/(\w+)$", rota)
        if m:
            cid, acao = int(m.group(1)), m.group(2)

            if acao == "ajustar":
                campos, valores = [], []
                for k in ("inicio", "fim", "titulo", "legenda"):
                    if k in corpo:
                        campos.append(f"{k}=?")
                        valores.append(corpo[k])
                if "hashtags" in corpo:
                    campos.append("hashtags=?")
                    valores.append(json.dumps(corpo["hashtags"], ensure_ascii=False))
                if campos:
                    db.ex(f"UPDATE candidato SET {','.join(campos)} WHERE id=?", (*valores, cid))
                return self._json({"ok": True})

            if acao == "montar":
                def tarefa():
                    try:
                        TRABALHO.recado = f"montando o clipe {cid}"
                        pipeline.montar_clipe(cid, config.carregar(), PLATAFORMA)
                        TRABALHO.recado = f"clipe {cid} pronto"
                    except Exception as e:
                        db.ex("UPDATE candidato SET estado='erro' WHERE id=?", (cid,))
                        TRABALHO.recado = f"nao consegui montar o clipe {cid}: {e}"
                db.ex("UPDATE candidato SET estado='montando' WHERE id=?", (cid,))
                threading.Thread(target=tarefa, daemon=True).start()
                return self._json({"ok": True})

            if acao == "agendar":
                db.ex("UPDATE candidato SET estado='agendado', agendado_para=?, redes=? WHERE id=?",
                      (corpo.get("quando", ""), json.dumps(corpo.get("redes", []),
                                                           ensure_ascii=False), cid))
                return self._json({"ok": True})

            if acao == "descartar":
                db.ex("UPDATE candidato SET estado='descartado' WHERE id=?", (cid,))
                return self._json({"ok": True})

        m = re.match(r"^/api/sessao/(\d+)/limpar$", rota)
        if m:
            liberado = pipeline.limpar_bruto(int(m.group(1)))
            return self._json({"liberado_gb": round(liberado / 1e9, 2)})

        if rota == "/api/perfil/salvar":
            nome = re.sub(r"[^a-z0-9_-]", "", (corpo.get("id") or "meu").lower()) or "meu"
            base = s_gta.carregar_perfil(corpo.get("base", "generico"), config.PASTA_PERFIS)
            base["nome"] = corpo.get("nome") or base.get("nome", nome)
            base["calibrado"] = True
            base["regioes"].update(corpo.get("regioes") or {})
            (config.PASTA_PERFIS / f"{nome}.json").write_text(
                json.dumps(base, ensure_ascii=False, indent=2), "utf-8")
            return self._json({"ok": True, "id": nome, "perfis": _perfis()})

        return self._json({"erro": "rota desconhecida"}, 404)


def subir(porta: int = 8777) -> ThreadingHTTPServer:
    for p in (config.PASTA_PERFIS,):
        for origem in (Path(__file__).resolve().parent.parent / "perfis").glob("*.json"):
            alvo = p / origem.name
            if not alvo.exists():
                alvo.write_text(origem.read_text("utf-8"), "utf-8")
    s = ThreadingHTTPServer(("127.0.0.1", porta), Mao)
    return s
