"""Entrada de video e chat da Twitch, sem login nem chave de API.

VOD: baixado com yt-dlp a partir do link ou do canal.
Ao vivo: ffmpeg copia o HLS em pedacos (praticamente zero de CPU).
Chat: conexao anonima no IRC da Twitch, cada mensagem com hora.
"""
from __future__ import annotations

import json
import random
import re
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path

from .config import PASTA_BRUTO, PASTA_DADOS

IRC_HOST, IRC_PORTA = "irc.chat.twitch.tv", 6697
_TAG = re.compile(r"^@(?P<tags>[^ ]*) :(?P<nick>[^!]+)![^ ]+ PRIVMSG #(?P<canal>[^ ]+) :(?P<msg>.*)$")


def _ytdlp(*args: str, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(["yt-dlp", *args], capture_output=True, text=True, timeout=timeout)


def esta_ao_vivo(canal: str) -> dict:
    """Devolve {'ao_vivo': bool, 'titulo': str, 'url': str}."""
    url = f"https://www.twitch.tv/{canal}"
    r = _ytdlp("-J", "--no-warnings", url, timeout=60)
    if r.returncode != 0:
        return {"ao_vivo": False, "titulo": "", "url": url, "erro": r.stderr.strip()[-300:]}
    try:
        d = json.loads(r.stdout)
    except Exception:
        return {"ao_vivo": False, "titulo": "", "url": url}
    return {"ao_vivo": bool(d.get("is_live")), "titulo": d.get("title") or "", "url": url}


def listar_vods(canal: str, limite: int = 12) -> list[dict]:
    r = _ytdlp("-J", "--flat-playlist", "--no-warnings",
               "--playlist-end", str(limite),
               f"https://www.twitch.tv/{canal}/videos", timeout=120)
    if r.returncode != 0:
        return []
    try:
        d = json.loads(r.stdout)
    except Exception:
        return []
    saida = []
    for e in d.get("entries") or []:
        saida.append({
            "id": e.get("id"),
            "titulo": e.get("title") or "sem titulo",
            "duracao": e.get("duration") or 0,
            "url": e.get("url") or f"https://www.twitch.tv/videos/{e.get('id')}",
        })
    return saida


def baixar_vod(url: str, destino: Path, qualidade: str = "best",
               progresso=None) -> Path:
    """Baixa o VOD inteiro. Chama progresso(fracao, texto) enquanto anda."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["yt-dlp", "--no-warnings", "--newline",
           "-f", f"{qualidade}[ext=mp4]/{qualidade}",
           "--concurrent-fragments", "4",
           "-o", str(destino), url]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    pat = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
    for linha in p.stdout:  # type: ignore[union-attr]
        m = pat.search(linha)
        if m and progresso:
            progresso(float(m.group(1)) / 100.0, "baixando o VOD")
    p.wait()
    if p.returncode != 0 or not destino.exists():
        raise RuntimeError("nao consegui baixar o VOD")
    return destino


def url_hls(canal: str) -> str:
    r = _ytdlp("-g", "-f", "best", "--no-warnings", f"https://www.twitch.tv/{canal}", timeout=60)
    linhas = [l for l in r.stdout.splitlines() if l.startswith("http")]
    if not linhas:
        raise RuntimeError("canal nao esta ao vivo ou o link nao veio")
    return linhas[0]


class GravadorAoVivo:
    """Copia a live em pedacos de N segundos, sem recodificar."""

    def __init__(self, canal: str, pasta: Path, segundos: int = 300, ffmpeg: str = "ffmpeg"):
        self.canal, self.pasta, self.segundos, self.ffmpeg = canal, pasta, segundos, ffmpeg
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.lista = self.pasta / "pedacos.csv"
        self.inicio_epoch = 0.0
        self.proc: subprocess.Popen | None = None

    def comecar(self) -> None:
        url = url_hls(self.canal)
        self.inicio_epoch = time.time()
        (self.pasta / "inicio.txt").write_text(str(self.inicio_epoch), "utf-8")
        cmd = [self.ffmpeg, "-hide_banner", "-loglevel", "error",
               "-i", url, "-c", "copy", "-f", "segment",
               "-segment_time", str(self.segundos),
               "-segment_list", str(self.lista),
               "-segment_list_type", "csv",
               "-reset_timestamps", "1",
               str(self.pasta / "pedaco_%05d.ts")]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def pedacos_prontos(self) -> list[dict]:
        """Pedacos ja fechados, com inicio e fim em segundos desde o comeco."""
        if not self.lista.exists():
            return []
        saida = []
        for linha in self.lista.read_text("utf-8").splitlines():
            partes = linha.split(",")
            if len(partes) != 3:
                continue
            nome, ini, fim = partes
            caminho = self.pasta / nome
            if caminho.exists():
                saida.append({"arquivo": str(caminho), "inicio": float(ini), "fim": float(fim)})
        return saida

    def parar(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()


class ChatLogger:
    """Le o chat da Twitch sem login e grava jsonl com a hora de cada mensagem."""

    def __init__(self, canal: str, arquivo: Path):
        self.canal = canal.lower()
        self.arquivo = arquivo
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._parar = threading.Event()
        self._t: threading.Thread | None = None
        self.inicio_epoch = 0.0
        self.total = 0

    def comecar(self) -> None:
        self.inicio_epoch = time.time()
        self._t = threading.Thread(target=self._rodar, daemon=True)
        self._t.start()

    def _rodar(self) -> None:
        while not self._parar.is_set():
            try:
                self._sessao()
            except Exception:
                time.sleep(5)

    def _sessao(self) -> None:
        ctx = ssl.create_default_context()
        with socket.create_connection((IRC_HOST, IRC_PORTA), timeout=20) as cru:
            with ctx.wrap_socket(cru, server_hostname=IRC_HOST) as s:
                nick = f"justinfan{random.randint(10000, 99999)}"
                s.sendall(b"CAP REQ :twitch.tv/tags\r\n")
                s.sendall(f"NICK {nick}\r\n".encode())
                s.sendall(f"JOIN #{self.canal}\r\n".encode())
                buf = ""
                with self.arquivo.open("a", encoding="utf-8") as f:
                    while not self._parar.is_set():
                        try:
                            dados = s.recv(8192).decode("utf-8", "ignore")
                        except socket.timeout:
                            continue
                        if not dados:
                            return
                        buf += dados
                        while "\r\n" in buf:
                            linha, buf = buf.split("\r\n", 1)
                            if linha.startswith("PING"):
                                s.sendall(b"PONG :tmi.twitch.tv\r\n")
                                continue
                            m = _TAG.match(linha)
                            if not m:
                                continue
                            f.write(json.dumps({
                                "t": time.time(),
                                "usuario": m.group("nick"),
                                "texto": m.group("msg"),
                            }, ensure_ascii=False) + "\n")
                            f.flush()
                            self.total += 1

    def parar(self) -> None:
        self._parar.set()
