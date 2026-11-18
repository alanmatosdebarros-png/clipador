const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let ESTADO = {}, SESSAO = null, PERFIL_BASE = "generico";

const api = async (rota, corpo) => {
  const op = corpo ? { method: "POST", headers: { "Content-Type": "application/json" },
                       body: JSON.stringify(corpo) } : {};
  const r = await fetch(rota, op);
  return r.json();
};
const seg = (s) => {
  s = Math.max(0, Math.round(s));
  const m = Math.floor(s / 60), r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
};
const hms = (s) => {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  return h ? `${h}h${String(m).padStart(2, "0")}` : `${m}:${String(r).padStart(2, "0")}`;
};

/* ---------------------------------------------------------------- telas */
$$(".passo").forEach(b => b.onclick = () => {
  $$(".passo").forEach(x => x.dataset.on = "0");
  b.dataset.on = "1";
  $$("section").forEach(s => s.dataset.on = s.dataset.tela === b.dataset.tela ? "1" : "0");
  if (b.dataset.tela === "momentos") carregarMomentos();
  if (b.dataset.tela === "fila") carregarFila();
});
const irPara = (tela) => $$(".passo").find(b => b.dataset.tela === tela)?.click();

$("#btTema").onclick = async () => {
  const novo = document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro";
  document.documentElement.dataset.tema = novo;
  localStorage.setItem("tema", novo);
  await api("/api/config", { tema: novo });
};
try { const t = localStorage.getItem("tema"); if (t) document.documentElement.dataset.tema = t; } catch (e) {}

/* ---------------------------------------------------------------- estado */
async function puxarEstado() {
  ESTADO = await api("/api/estado");
  const p = ESTADO.plataforma || {};
  $("#chipMaquina").textContent = p.descricao || "";
  const t = ESTADO.trabalho || {};
  $("#recado").textContent = t.recado || t.estado || "parado";
  $("#barra").style.width = Math.round((t.progresso || 0) * 100) + "%";
  $("#pontoVivo").dataset.on = t.rodando ? "1" : "0";
  $("#btParar").style.display = t.rodando ? "" : "none";
  desenharSessoes();
  if (!$("#canal").value) $("#canal").value = (ESTADO.config || {}).canal_twitch || "";
  $("#chipModo").textContent = "modo atual: " +
    ((ESTADO.config || {}).modo === "ao_vivo" ? "durante a live" : "depois da live");
  $("#infoPastas").textContent = "clipes em " + ((ESTADO.pastas || {}).clipes || "");
}

function desenharSessoes() {
  const alvo = $("#listaSessoes"), sel = $("#selSessao");
  const ss = ESTADO.sessoes || [];
  if (!ss.length) { alvo.innerHTML = '<div class="vazio">nenhuma sessao ainda</div>'; return; }
  alvo.innerHTML = ss.map(s => `
    <div class="item">
      <div class="cresce">
        <div class="t">${s.titulo || s.canal || "sessao " + s.id}</div>
        <div class="d">${s.origem === "live" ? "ao vivo" : "VOD"} · ${s.duracao ? hms(s.duracao) : "-"} · ${s.recado || s.estado}</div>
      </div>
      <button class="bt ghost pequeno" onclick="abrirSessao(${s.id})">Ver momentos</button>
    </div>`).join("");
  const atual = sel.value;
  sel.innerHTML = ss.map(s => `<option value="${s.id}">${s.id} · ${s.titulo || s.canal}</option>`).join("");
  if (atual && ss.some(s => String(s.id) === atual)) sel.value = atual;
  else if (!SESSAO && ss.length) SESSAO = ss[0].id;
  if (SESSAO) sel.value = SESSAO;
}
window.abrirSessao = (id) => { SESSAO = id; irPara("momentos"); };

/* ---------------------------------------------------------------- fonte */
$("#btChecar").onclick = async () => {
  const canal = $("#canal").value.trim();
  if (!canal) return;
  $("#estadoCanal").innerHTML = '<div class="chip">procurando...</div>';
  await api("/api/config", { canal_twitch: canal });
  const r = await api("/api/canal/checar", { canal });
  if (r.erro) { $("#estadoCanal").innerHTML = `<div class="aviso">${r.erro}</div>`; return; }
  const vods = (r.vods || []).map(v => `
    <div class="item">
      <div class="cresce"><div class="t">${v.titulo}</div><div class="d">${hms(v.duracao || 0)}</div></div>
      <button class="bt ghost pequeno" onclick="document.querySelector('#urlVod').value='${v.url}'">Usar</button>
    </div>`).join("");
  $("#estadoCanal").innerHTML =
    `<div class="chip" style="border-color:${r.ao_vivo ? "var(--ok)" : "var(--linha)"}">
       ${r.ao_vivo ? "esta ao vivo agora: " + (r.titulo || "") : "nao esta ao vivo"}</div>
     <div class="lista" style="margin-top:12px">${vods || '<div class="vazio">nenhum VOD guardado. Liga o "Store past broadcasts" no painel da Twitch pela web.</div>'}</div>`;
};
$("#btModoDepois").onclick = async () => { await api("/api/config", { modo: "depois" }); puxarEstado(); };
$("#btModoVivo").onclick = async () => { await api("/api/config", { modo: "ao_vivo" }); puxarEstado(); };

$("#btAnalisar").onclick = async () => {
  const url = $("#urlVod").value.trim();
  if (!url) return alert("cola o link do VOD ou escolhe um da lista");
  const r = await api("/api/vod/analisar", { url });
  if (r.erro) return alert(r.erro);
  SESSAO = r.sessao_id; irPara("momentos"); puxarEstado();
};
$("#btAoVivo").onclick = async () => {
  const r = await api("/api/live/comecar", { canal: $("#canal").value.trim() });
  if (r.erro) return alert(r.erro);
  SESSAO = r.sessao_id; puxarEstado();
};
$("#btParar").onclick = async () => { await api("/api/live/parar", {}); puxarEstado(); };

/* ------------------------------------------------------------- momentos */
$("#selSessao").onchange = (e) => { SESSAO = Number(e.target.value); carregarMomentos(); };
$("#btRecarregar").onclick = () => carregarMomentos();
$("#btLimpar").onclick = async () => {
  if (!SESSAO || !confirm("apaga o video bruto dessa sessao? os clipes ja montados ficam")) return;
  const r = await api(`/api/sessao/${SESSAO}/limpar`, {});
  alert(`liberou ${r.liberado_gb} GB`);
};

async function carregarMomentos() {
  if (!SESSAO) { $("#grade").innerHTML = '<div class="vazio">escolhe uma sessao</div>'; return; }
  const r = await api(`/api/sessao/${SESSAO}/candidatos`);
  const cs = (r.candidatos || []).filter(c => c.estado !== "descartado");
  if (!cs.length) {
    $("#grade").innerHTML = '<div class="vazio">ainda nao tem momento aqui. Se a analise esta rodando, espera o rodape.</div>';
    return;
  }
  $("#grade").innerHTML = cs.map(cartao).join("");
}

function cartao(c) {
  const sinais = Object.entries(c.sinais || {}).map(([k, v]) => `<span class="sinal">${k}</span>`).join("");
  const nota = Math.round((c.nota || 0) * 100);
  const temVideo = c.estado === "pronto" && c.arquivo;
  const midia = temVideo
    ? `<video controls preload="metadata" src="/arquivo?c=${encodeURIComponent(c.arquivo)}"></video>`
    : (c.capa ? `<img src="/arquivo?c=${encodeURIComponent(c.capa)}" style="width:100%;height:100%;object-fit:cover">`
              : `<span style="color:var(--fraco);font-size:13px">ainda nao montado</span>`);
  return `
  <article class="momento" data-id="${c.id}">
    <div class="capa">${midia}
      <div class="nota"><b>${nota}</b> / 100</div>
      <div class="tempo">${seg(c.duracao)} · ${hms(c.inicio)}</div>
    </div>
    <div class="corpo">
      <div class="sinais">${sinais || '<span class="sinal">sem sinal forte</span>'}</div>
      <div><label class="campo">titulo</label>
        <input type="text" value="${(c.titulo || "").replace(/"/g, "&quot;")}" onchange="ajustar(${c.id},'titulo',this.value)"></div>
      <div><label class="campo">legenda</label>
        <textarea onchange="ajustar(${c.id},'legenda',this.value)">${c.legenda || ""}</textarea></div>
      <div class="sinais">${(c.hashtags || []).map(h => `<span class="sinal">#${h}</span>`).join("")}</div>
      ${c.transcricao ? `<div class="fala">${c.transcricao}</div>` : ""}
      <div class="linha" style="gap:8px">
        <div style="flex:1"><label class="campo">inicio (s)</label>
          <input type="number" step="0.5" value="${c.inicio}" onchange="ajustar(${c.id},'inicio',Number(this.value))"></div>
        <div style="flex:1"><label class="campo">fim (s)</label>
          <input type="number" step="0.5" value="${c.fim}" onchange="ajustar(${c.id},'fim',Number(this.value))"></div>
      </div>
      <div class="acoes">
        <span class="estado" data-e="${c.estado}">${c.estado}</span>
        <div style="flex:1"></div>
        ${temVideo ? `<a class="bt ghost pequeno" href="/arquivo?c=${encodeURIComponent(c.arquivo)}&baixar=1">Baixar</a>` : ""}
        ${temVideo ? `<button class="bt pequeno" onclick="agendar(${c.id})">Pra fila</button>`
                   : `<button class="bt pequeno" onclick="montar(${c.id})">Montar</button>`}
        <button class="bt perigo pequeno" onclick="descartar(${c.id})">Fora</button>
      </div>
    </div>
  </article>`;
}

window.ajustar = (id, campo, valor) => api(`/api/candidato/${id}/ajustar`, { [campo]: valor });
window.montar = async (id) => {
  const el = document.querySelector(`.momento[data-id="${id}"] .estado`);
  if (el) { el.textContent = "montando"; el.dataset.e = "montando"; }
  await api(`/api/candidato/${id}/montar`, {});
  const olho = setInterval(async () => {
    const r = await api(`/api/sessao/${SESSAO}/candidatos`);
    const c = (r.candidatos || []).find(x => x.id === id);
    if (c && c.estado !== "montando") { clearInterval(olho); carregarMomentos(); }
  }, 4000);
};
window.descartar = async (id) => { await api(`/api/candidato/${id}/descartar`, {}); carregarMomentos(); };
window.agendar = async (id) => {
  const quando = prompt("quando postar? (ex: 2026-11-20 19:30)", "");
  if (quando === null) return;
  await api(`/api/candidato/${id}/agendar`, { quando, redes: ["tiktok", "reels", "shorts"] });
  irPara("fila");
};

/* ----------------------------------------------------------------- fila */
async function carregarFila() {
  const r = await api("/api/fila");
  const f = r.fila || [];
  $("#listaFila").innerHTML = f.length ? f.map(c => `
    <div class="item">
      <div class="cresce">
        <div class="t">${c.titulo || "sem titulo"}</div>
        <div class="d">${c.agendado_para || "sem horario"} · ${(JSON.parse(c.redes || "[]")).join(", ") || "sem rede"}</div>
        <div class="d">${c.legenda || ""} ${(c.hashtags || []).map(h => "#" + h).join(" ")}</div>
      </div>
      ${c.arquivo ? `<a class="bt ghost pequeno" href="/arquivo?c=${encodeURIComponent(c.arquivo)}&baixar=1">Baixar</a>` : ""}
    </div>`).join("") : '<div class="vazio">nada na fila ainda</div>';
}

/* -------------------------------------------------------------- ajustes */
const CAMPOS = ["duracao_alvo", "duracao_minima", "duracao_maxima", "intervalo_minimo",
  "maximo_candidatos", "fps_saida", "volume_alvo_lufs", "legenda", "bipar_palavrao",
  "inserto_minimapa", "capa_automatica", "chave_claude", "apagar_bruto_depois", "limite_disco_gb"];

function preencherAjustes() {
  const c = ESTADO.config || {};
  CAMPOS.forEach(k => {
    const el = $("#cfg_" + k); if (!el) return;
    el.value = typeof c[k] === "boolean" ? (c[k] ? "1" : "0") : (c[k] ?? "");
  });
  const sel = $("#cfg_perfil_hud");
  sel.innerHTML = (ESTADO.perfis || []).map(p =>
    `<option value="${p.id}">${p.nome}${p.calibrado ? "" : " (nao calibrado)"}</option>`).join("");
  sel.value = c.perfil_hud || "generico";
  PERFIL_BASE = sel.value;
}
$("#btSalvar").onclick = async () => {
  const novo = {};
  CAMPOS.forEach(k => {
    const el = $("#cfg_" + k); if (!el) return;
    const orig = (ESTADO.config || {})[k];
    novo[k] = typeof orig === "boolean" ? el.value === "1"
            : typeof orig === "number" ? Number(el.value) : el.value;
  });
  novo.perfil_hud = $("#cfg_perfil_hud").value;
  await api("/api/config", novo);
  await puxarEstado(); preencherAjustes();
  $("#btSalvar").textContent = "salvo"; setTimeout(() => $("#btSalvar").textContent = "Salvar tudo", 1500);
};

/* ------------------------------------------------------------- calibrar */
let REGIOES = {}, arrastando = null;
$("#btCalibrar").onclick = () => {
  const a = $("#areaCalib");
  a.style.display = a.style.display === "none" ? "" : "none";
  PERFIL_BASE = $("#cfg_perfil_hud").value;
};
$("#arqPrint").onchange = (e) => {
  const f = e.target.files[0]; if (!f) return;
  const url = URL.createObjectURL(f);
  $("#calib").innerHTML = `<img src="${url}" id="imgCalib">`;
  REGIOES = {};
};
$("#calib").addEventListener("mousedown", (e) => {
  const img = $("#imgCalib"); if (!img) return;
  const r = img.getBoundingClientRect();
  arrastando = { x: e.clientX - r.left, y: e.clientY - r.top, r };
});
$("#calib").addEventListener("mouseup", (e) => {
  if (!arrastando) return;
  const { x, y, r } = arrastando; arrastando = null;
  const x2 = e.clientX - r.left, y2 = e.clientY - r.top;
  const rx = Math.min(x, x2) / r.width, ry = Math.min(y, y2) / r.height;
  const rw = Math.abs(x2 - x) / r.width, rh = Math.abs(y2 - y) / r.height;
  if (rw < 0.01 || rh < 0.01) return;
  const nome = $("#selRegiao").value;
  REGIOES[nome] = { x: +rx.toFixed(4), y: +ry.toFixed(4), w: +rw.toFixed(4), h: +rh.toFixed(4) };
  desenharCaixas();
});
function desenharCaixas() {
  $$("#calib .caixa").forEach(c => c.remove());
  const img = $("#imgCalib"); if (!img) return;
  Object.entries(REGIOES).forEach(([nome, r]) => {
    const d = document.createElement("div");
    d.className = "caixa";
    d.style.left = r.x * 100 + "%"; d.style.top = r.y * 100 + "%";
    d.style.width = r.w * 100 + "%"; d.style.height = r.h * 100 + "%";
    d.innerHTML = `<span>${nome}</span>`;
    $("#calib").appendChild(d);
  });
}
$("#btSalvarPerfil").onclick = async () => {
  if (!Object.keys(REGIOES).length) return alert("marca pelo menos uma regiao no print");
  const id = prompt("nome do perfil (sem espaco)", "gta6");
  if (!id) return;
  const r = await api("/api/perfil/salvar", { id, nome: id.toUpperCase(), base: PERFIL_BASE, regioes: REGIOES });
  await api("/api/config", { perfil_hud: r.id });
  await puxarEstado(); preencherAjustes();
  alert("perfil salvo e ja selecionado");
};

/* ------------------------------------------------------------------ loop */
(async () => {
  await puxarEstado();
  preencherAjustes();
  setInterval(async () => {
    const antes = (ESTADO.trabalho || {}).estado;
    await puxarEstado();
    if ((ESTADO.trabalho || {}).estado !== antes &&
        $('section[data-tela="momentos"]').dataset.on === "1") carregarMomentos();
  }, 3000);
})();
