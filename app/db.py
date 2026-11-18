"""Banco local (sqlite). Guarda sessoes, candidatos e clipes."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .config import BANCO

ESQUEMA = """
CREATE TABLE IF NOT EXISTS sessao (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  canal TEXT, titulo TEXT, origem TEXT, modo TEXT,
  caminho_video TEXT, duracao REAL, fps REAL, largura INTEGER, altura INTEGER,
  criada_em REAL, estado TEXT, progresso REAL, recado TEXT
);
CREATE TABLE IF NOT EXISTS candidato (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sessao_id INTEGER, pico REAL, inicio REAL, fim REAL,
  nota REAL, sinais TEXT, resumo TEXT, transcricao TEXT,
  titulo TEXT, legenda TEXT, hashtags TEXT,
  estado TEXT DEFAULT 'candidato',
  arquivo TEXT, capa TEXT, agendado_para TEXT, redes TEXT,
  criado_em REAL
);
CREATE TABLE IF NOT EXISTS evento (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sessao_id INTEGER, t REAL, tipo TEXT, detalhe TEXT
);
CREATE INDEX IF NOT EXISTS ix_cand_sessao ON candidato(sessao_id);
CREATE INDEX IF NOT EXISTS ix_ev_sessao ON evento(sessao_id);
"""


def conectar() -> sqlite3.Connection:
    c = sqlite3.connect(BANCO, check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


_con = conectar()
_con.executescript(ESQUEMA)
_con.commit()


def ex(sql: str, args: tuple = ()) -> sqlite3.Cursor:
    cur = _con.execute(sql, args)
    _con.commit()
    return cur


def um(sql: str, args: tuple = ()) -> dict | None:
    r = _con.execute(sql, args).fetchone()
    return dict(r) if r else None


def todos(sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in _con.execute(sql, args).fetchall()]


def nova_sessao(canal: str, titulo: str, origem: str, modo: str) -> int:
    cur = ex(
        "INSERT INTO sessao (canal,titulo,origem,modo,criada_em,estado,progresso,recado)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (canal, titulo, origem, modo, time.time(), "criada", 0.0, ""),
    )
    return int(cur.lastrowid)


def atualizar_sessao(sid: int, **campos: Any) -> None:
    if not campos:
        return
    cols = ",".join(f"{k}=?" for k in campos)
    ex(f"UPDATE sessao SET {cols} WHERE id=?", (*campos.values(), sid))


def salvar_candidatos(sid: int, candidatos: list[dict]) -> None:
    ex("DELETE FROM candidato WHERE sessao_id=? AND estado='candidato'", (sid,))
    for c in candidatos:
        ex(
            "INSERT INTO candidato (sessao_id,pico,inicio,fim,nota,sinais,resumo,transcricao,"
            "titulo,legenda,hashtags,estado,criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, c["pico"], c["inicio"], c["fim"], c["nota"],
             json.dumps(c.get("sinais", {}), ensure_ascii=False),
             c.get("resumo", ""), c.get("transcricao", ""),
             c.get("titulo", ""), c.get("legenda", ""),
             json.dumps(c.get("hashtags", []), ensure_ascii=False),
             "candidato", time.time()),
        )
