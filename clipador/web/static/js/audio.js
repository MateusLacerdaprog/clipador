// Clipador - aba 4 Audio: 4 trilhas, bibliotecas e previa.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// --------------------------------------------------------------------- 4 AUDIO
// Timeline com 4 trilhas independentes + painel da trilha selecionada. Tudo salva na hora.
const TRILHAS = [
  { id: "original", nome: "Som original", dica: "o áudio dos trechos do vídeo" },
  { id: "musica", nome: "Música", dica: "trilha de fundo da biblioteca" },
  { id: "narracao", nome: "Narração", dica: "sua voz (gravada ou importada)" },
  { id: "efeitos", nome: "Efeitos", dica: "sons curtos em pontos do vídeo" },
];
const NOME_TRILHA = Object.fromEntries(TRILHAS.map((t) => [t.id, t.nome]));
let trilhaSel = "original", cursorT = 0, previaChave = null, previaSolo = null, analiseNarr = null;
const biblio = { musicas: [], efeitos: [] };
const fmtDb = (v) => (v > 0 ? "+" : "") + (+v).toFixed(0) + " dB";
const pct = (t) => `${Math.max(0, Math.min(100, (t / Math.max(P.duracao, 0.01)) * 100))}%`;
const chaveAudio = () => JSON.stringify([P.audio, P.segmentos.map((s) => [s.ini, s.fim, s.audio]), P.narracao, P.narracao_dur]);

async function carregarBiblio(tipo) { biblio[tipo] = await api("GET", `/api/biblioteca/${tipo}`); }
const durBiblio = (tipo, nome) => (biblio[tipo].find((m) => m.nome === nome) || {}).dur;

function blocosDaTrilha(id) {
  const A = P.audio, T = P.duracao, out = [];
  if (id === "original") {
    let t = 0;
    P.segmentos.forEach((s, i) => {
      const d = s.fim - s.ini, cfg = s.audio || {}, modo = cfg.modo || "padrao";
      const rot = modo === "mudo" ? "mudo" : modo === "volume" ? fmtDb(cfg.db ?? 0) : "padrão";
      out.push({ ini: t, fim: t + d, cls: modo === "mudo" ? "mudo" : modo === "volume" ? "proprio" : "", rot: `T${i + 1} · ${rot}`, seg: i });
      t += d;
    });
  } else if (id === "musica" && A.musica.arquivo) {
    const m = A.musica, ini = Math.min(m.inicio_video, T);
    let fim = m.fim_video == null ? T : Math.min(Math.max(m.fim_video, ini), T);
    const dArq = durBiblio("musicas", m.arquivo);
    if (!m.loop && dArq) fim = Math.min(fim, ini + Math.max(dArq - m.inicio_arquivo, 0));
    out.push({ ini, fim, rot: `${m.arquivo} · ${fmtDb(m.db)}`, fadeIn: m.fade_in, fadeOut: m.fade_out,
      cls: dArq == null ? "faltando" : "" });
  } else if (id === "narracao" && P.narracao) {
    const n = A.narracao, ini = Math.max(n.deslocamento, 0);
    const util = Math.max(P.narracao_dur - Math.max(-n.deslocamento, 0), 0);
    out.push({ ini, fim: Math.min(ini + util, T), rot: `voz · ${fmtDb(n.db)}`, fadeIn: n.fade_in, fadeOut: n.fade_out });
    if (ini + util > T + 0.05) out.push({ ini: T, fim: T, cls: "cortado", rot: `+${(ini + util - T).toFixed(1)} s cortados` });
  } else if (id === "efeitos") {
    A.efeitos.forEach((e, i) => {
      const d = e.dur || Math.max((durBiblio("efeitos", e.arquivo) || 0.5) - e.inicio_arquivo, 0.1);
      out.push({ ini: e.em, fim: Math.min(e.em + d, T), rot: e.arquivo || "?", cls: e.ativo ? "" : "mudo", fx: i });
    });
  }
  return out;
}

function trilhaAtiva(id) {
  const A = P.audio;
  if (id === "efeitos") return A.efeitos.some((e) => e.ativo);
  return A[id].ativo;
}

function preservarFoco(raiz, fn) {   // redesenhar com innerHTML perde o foco: devolve ao mesmo botao
  const a = document.activeElement;
  const sel = a && raiz.contains(a) ? ["data-mute", "data-solo", "data-foco-trilha"].map((k) => (a.hasAttribute(k) ? `[${k}="${a.getAttribute(k)}"]` : null)).find(Boolean) : null;
  fn();
  if (sel) raiz.querySelector(sel)?.focus();
}
function renderTimelineAudio() { preservarFoco($("#tl-audio"), renderTimelineAudioBruto); }
function renderTimelineAudioBruto() {
  const T = P.duracao, passo = T > 120 ? 30 : T > 40 ? 10 : T > 15 ? 5 : 1;
  let regua = "";
  for (let t = 0; t <= T + 0.001; t += passo) regua += `<span style="left:${pct(t)}">${mmss(t).replace(".0", "")}</span>`;
  $("#tl-audio").innerHTML = `<div class="tl-regua"><div class="tl-cab"></div><div class="tl-pista">${regua}</div></div>` +
    TRILHAS.map((tr) => {
      const ativa = trilhaAtiva(tr.id), vazia = (tr.id === "musica" && !P.audio.musica.arquivo) ||
        (tr.id === "narracao" && !P.narracao) || (tr.id === "efeitos" && !P.audio.efeitos.length);
      const blocos = blocosDaTrilha(tr.id).map((b) => {
        const fi = b.fadeIn ? `<i class="fade-in" style="width:${Math.min(50, (b.fadeIn / Math.max(b.fim - b.ini, 0.01)) * 100)}%"></i>` : "";
        const fo = b.fadeOut ? `<i class="fade-out" style="width:${Math.min(50, (b.fadeOut / Math.max(b.fim - b.ini, 0.01)) * 100)}%"></i>` : "";
        return `<div class="tl-bloco b-${tr.id} ${b.cls || ""}" style="left:${pct(b.ini)};width:calc(${pct(b.fim - b.ini)} + ${b.cls === "cortado" ? "0px" : "1px"})"
          ${b.seg != null ? `data-seg="${b.seg}"` : ""} ${b.fx != null ? `data-fx="${b.fx}"` : ""} title="${esc(b.rot)} (${mmss(b.ini)}–${mmss(b.fim)})">${fi}${fo}<span>${esc(b.rot)}</span></div>`;
      }).join("") || `<span class="tl-vazio">${tr.id === "narracao" ? "sem narração — grave na aba 5 ou importe aqui" : tr.id === "musica" ? "sem música — escolha uma no painel" : tr.id === "efeitos" ? "sem efeitos" : ""}</span>`;
      return `<div class="tl-linha ${trilhaSel === tr.id ? "sel" : ""} ${ativa || vazia ? "" : "inativa"}" data-trilha="${tr.id}">
        <div class="tl-cab" title="${tr.dica}"><button type="button" class="trilha-nome" data-foco-trilha="${tr.id}" aria-pressed="${trilhaSel === tr.id}" aria-label="Editar a trilha ${tr.nome}">${tr.nome}</button>
          <button class="mini ${ativa ? "" : "desligada"}" data-mute="${tr.id}" aria-pressed="${!ativa}" aria-label="Desligar a trilha ${tr.nome}" title="ligar/desligar esta trilha" ${vazia ? "disabled" : ""}>M</button>
          <button class="mini" data-solo="${tr.id}" aria-label="Ouvir só a trilha ${tr.nome}" title="ouvir só esta trilha" ${vazia ? "disabled" : ""}>S</button></div>
        <div class="tl-pista">${blocos}</div></div>`;
    }).join("") + `<div id="tl-cursor" style="left:calc(150px + (100% - 150px) * ${cursorT / Math.max(T, 0.01)})"></div>`;
}

function renderResumoAudio() {
  const A = P.audio, L = [];
  const temVoz = P.narracao && A.narracao.ativo;
  if (!A.original.ativo) L.push("Som original: <b>desligado</b>");
  else {
    const mudos = P.segmentos.filter((s) => (s.audio || {}).modo === "mudo").length;
    L.push(`Som original: ${fmtDb(temVoz ? A.original.db_com_narracao : A.original.db)}${mudos ? ` (${mudos} trecho(s) mudo)` : ""}`);
  }
  L.push(A.musica.arquivo ? (A.musica.ativo ? `Música: ${esc(A.musica.arquivo)} a ${fmtDb(A.musica.db)}` : "Música: <b>desligada</b>") : "Música: nenhuma");
  L.push(P.narracao ? (A.narracao.ativo ? `Narração: ${P.narracao_dur.toFixed(1)} s a ${fmtDb(A.narracao.db)}${A.narracao.tratamento ? " (com tratamento de voz)" : ""}` : "Narração: <b>desligada</b>") : "Narração: nenhuma");
  const fx = A.efeitos.filter((e) => e.ativo).length;
  L.push(`Efeitos: ${fx}`);
  L.push(`Ducking: ${A.mix.ducking ? A.mix.ducking_forca : "desligado"} · Normalização: ${A.mix.normalizar ? "−14 LUFS" : "desligada"}`);
  $("#resumo-audio").innerHTML = L.map((x) => `<li>${x}</li>`).join("");
}

const campoNum = (rot, path, v, o = {}) =>
  `<label>${rot} <input type="number" data-a="${path}" value="${v ?? ""}" step="${o.step ?? 0.1}" ${o.min != null ? `min="${o.min}"` : ""} ${o.max != null ? `max="${o.max}"` : ""} placeholder="${o.ph || ""}" class="curto"> ${o.un || "s"}</label>`;
const campoDb = (rot, path, v, min = -40, max = 6) =>
  `<label class="db">${rot} <input type="range" data-a="${path}" min="${min}" max="${max}" step="1" value="${v}"> <b>${fmtDb(v)}</b></label>`;
const campoChk = (rot, path, v) => `<label><input type="checkbox" data-a="${path}" ${v ? "checked" : ""}> ${rot}</label>`;
const opcoesBiblio = (tipo, atual) => `<option value="">— nenhum —</option>` +
  biblio[tipo].map((m) => `<option value="${esc(m.nome)}" ${m.nome === atual ? "selected" : ""}>${esc(m.nome)} (${m.dur} s)</option>`).join("") +
  (atual && !biblio[tipo].some((m) => m.nome === atual) ? `<option value="${esc(atual)}" selected>${esc(atual)} (ARQUIVO FALTANDO)</option>` : "");
const blocoBiblioteca = (tipo) => `
  <details class="biblio"><summary>Adicionar à biblioteca de ${tipo === "musicas" ? "músicas" : "efeitos"}</summary>
    <div class="linha"><input type="file" data-up="${tipo}" accept="audio/*,video/mp4"><button data-enviar="${tipo}">Enviar</button></div>
    <div class="linha"><input data-url="${tipo}" class="cresce" placeholder="ou link (YouTube etc.) — baixa só o áudio"><button data-baixar="${tipo}">Baixar</button></div>
    <div class="tarefa" id="tarefa-biblio-${tipo}"></div>
    <p class="dica">Fica na pasta <b>${tipo}/</b> e vale para todos os projetos. Use só áudio que você tem direito de usar: músicas de jogos e de artistas têm direitos autorais e podem gerar bloqueio ou monetização para o dono nas plataformas.</p>
  </details>`;

function renderPainelTrilha() {
  const A = P.audio, el = $("#painel-trilha"), temVoz = P.narracao && A.narracao.ativo;
  let h = `<h3>${NOME_TRILHA[trilhaSel]}</h3>`;
  if (trilhaSel === "original") {
    const o = A.original;
    h += `<div class="linha">${campoChk("Trilha ligada", "original.ativo", o.ativo)}</div>
      <div class="linha">${campoDb("Volume sem narração", "original.db", o.db, -40, 12)}</div>
      <div class="linha">${campoDb("Volume quando há narração", "original.db_com_narracao", o.db_com_narracao, -40, 12)}</div>
      <p class="dica">Agora vale: <b>${temVoz ? "com narração" : "sem narração"}</b>. Para trocar o som original por outro áudio, desligue esta trilha e use Música ou Efeitos.</p>
      <h4>Por trecho</h4><table class="tabela"><tbody>` +
      P.segmentos.map((s, i) => {
        const c = s.audio || { modo: "padrao", db: 0 };
        return `<tr><td>T${i + 1}</td><td class="dica">${mmss(s.ini)}–${mmss(s.fim)} da fonte</td>
          <td><select data-seg-i="${i}" data-seg-k="modo" aria-label="Volume do trecho ${i + 1}">${["padrao", "volume", "mudo"].map((m) => `<option value="${m}" ${c.modo === m ? "selected" : ""}>${{ padrao: "volume da trilha", volume: "volume próprio", mudo: "mudo" }[m]}</option>`).join("")}</select></td>
          <td>${c.modo === "volume" ? `<input type="number" class="curto" step="1" min="-60" max="12" data-seg-i="${i}" data-seg-k="db" value="${c.db ?? 0}"> dB` : ""}</td></tr>`;
      }).join("") + `</tbody></table>`;
  } else if (trilhaSel === "musica") {
    const m = A.musica;
    h += `<div class="linha"><select data-a="musica.arquivo" class="cresce" aria-label="Música da biblioteca">${opcoesBiblio("musicas", m.arquivo)}</select>
        ${m.arquivo ? `<button data-remover-biblio="musicas" data-nome="${esc(m.arquivo)}" title="apaga o arquivo da pasta musicas/">Excluir da biblioteca</button>` : ""}</div>
      ${m.arquivo ? `<audio controls preload="none" src="/api/biblioteca/musicas/${encodeURIComponent(m.arquivo)}/arquivo" style="width:100%"></audio>` : ""}
      <div class="linha">${campoChk("Trilha ligada", "musica.ativo", m.ativo)} ${campoChk("Repetir se acabar", "musica.loop", m.loop)}</div>
      <div class="linha">${campoDb("Volume", "musica.db", m.db, -40, 6)}</div>
      <div class="linha">${campoNum("Entra no vídeo em", "musica.inicio_video", m.inicio_video, { min: 0 })}
        ${campoNum("Sai em", "musica.fim_video", m.fim_video, { min: 0, ph: "fim" })}
        <button class="mini" data-cursor-para="musica.inicio_video" title="usar a posição do cursor">⌖ cursor</button></div>
      <div class="linha">${campoNum("Começar o arquivo em", "musica.inicio_arquivo", m.inicio_arquivo, { min: 0, step: 0.5 })}
        ${campoNum("Fade-in", "musica.fade_in", m.fade_in, { min: 0, max: 10 })} ${campoNum("Fade-out", "musica.fade_out", m.fade_out, { min: 0, max: 10 })}</div>
      ${blocoBiblioteca("musicas")}`;
  } else if (trilhaSel === "narracao") {
    const n = A.narracao;
    h += P.narracao ? `<p>${esc(P.narracao)} · ${P.narracao_dur.toFixed(1)} s</p><div id="analise-narr" class="dica">analisando…</div>`
      : `<p class="dica">Sem narração. Grave na aba <b>5 · Narração</b> ou importe um arquivo abaixo.</p>`;
    h += `<div class="linha"><label>Importar áudio <input type="file" id="narr-import" accept="audio/*"></label><button id="narr-import-ok">Importar</button></div>`;
    if (P.narracao) h += `<div class="linha">${campoChk("Trilha ligada", "narracao.ativo", n.ativo)} ${campoChk("Tratamento de voz (ruído, EQ, de-esser, compressor)", "narracao.tratamento", n.tratamento)}</div>
      <div class="linha">${campoDb("Volume", "narracao.db", n.db, -20, 12)}</div>
      <div class="linha">${campoNum("Deslocamento", "narracao.deslocamento", n.deslocamento, { step: 0.05 })}
        <span class="dica">+ atrasa a voz · − corta o começo (a legenda acompanha)</span></div>
      <div class="linha">${campoNum("Fade-in", "narracao.fade_in", n.fade_in, { min: 0, max: 5 })} ${campoNum("Fade-out", "narracao.fade_out", n.fade_out, { min: 0, max: 5 })}</div>`;
  } else {
    h += `<div class="linha"><button id="fx-add" class="primario">+ Efeito no cursor (${mmss(cursorT)})</button>
      <span class="dica">Clique na timeline para mover o cursor.</span></div>` +
      (A.efeitos.map((e, i) => `<div class="fx ${e.ativo ? "" : "inativa"}">
        <div class="linha"><b>#${i + 1}</b><select data-fx-i="${i}" data-fx-k="arquivo" class="cresce" aria-label="Arquivo do efeito ${i + 1}">${opcoesBiblio("efeitos", e.arquivo)}</select>
          <label><input type="checkbox" data-fx-i="${i}" data-fx-k="ativo" ${e.ativo ? "checked" : ""}> ligado</label>
          <button class="mini" data-fx-del="${i}" title="remover este efeito" aria-label="Remover o efeito ${i + 1}">✕</button></div>
        <div class="linha"><label>em <input type="number" class="curto" step="0.05" min="0" data-fx-i="${i}" data-fx-k="em" value="${e.em}"> s</label>
          <button class="mini" data-fx-cursor="${i}">⌖ cursor</button>
          <label class="db">vol <input type="range" min="-40" max="6" step="1" data-fx-i="${i}" data-fx-k="db" value="${e.db}"> <b>${fmtDb(e.db)}</b></label></div>
        <div class="linha"><label>início no arquivo <input type="number" class="curto" step="0.05" min="0" data-fx-i="${i}" data-fx-k="inicio_arquivo" value="${e.inicio_arquivo}"> s</label>
          <label>duração <input type="number" class="curto" step="0.05" min="0.05" data-fx-i="${i}" data-fx-k="dur" value="${e.dur ?? ""}" placeholder="inteiro"> s</label>
          <label>fade <input type="number" class="curto" step="0.05" min="0" data-fx-i="${i}" data-fx-k="fade_out" value="${e.fade_out}"> s</label></div></div>`).join("") ||
        `<p class="dica">Nenhum efeito. Coloque sons curtos (whoosh, impacto, notificação) na biblioteca e adicione no cursor.</p>`) +
      blocoBiblioteca("efeitos");
  }
  el.innerHTML = h;
  if (trilhaSel === "narracao" && P.narracao) mostrarAnaliseNarr();
}

async function mostrarAnaliseNarr() {
  try {
    const chave = `${P.nome}:${P.narracao_dur}`;
    if (!analiseNarr || analiseNarr.chave !== chave) analiseNarr = { chave, ...(await api("GET", `${base()}/narracao/analise`)) };
    const a = analiseNarr, el = $("#analise-narr"); if (!el) return;
    el.innerHTML = `pico ${a.pico_db} dBFS · nível médio ${a.rms_db} dBFS · clipping ${a.clip_pct}%` +
      (a.avisos.length ? `<div class="alerta">⚠ ${a.avisos.map(esc).join("<br>⚠ ")}</div>` : ` <span class="selo ok">sem estouro</span>`);
  } catch (e) { const el = $("#analise-narr"); if (el) el.textContent = "não consegui analisar: " + e.message; }
}

function renderMix() {
  $$("[data-mix]").forEach((i) => { const v = P.audio.mix[i.dataset.mix]; if (i.type === "checkbox") i.checked = !!v; else i.value = v; });
}

function renderOuvindo() {
  const o = $("#ouvindo");
  if (!previaChave) { o.textContent = "nenhuma prévia gerada"; o.className = "selo"; return; }
  const txt = previaSolo ? `ouvindo: só ${NOME_TRILHA[previaSolo]} (volume real, sem normalização)` : "ouvindo: mixagem final";
  const velha = previaChave !== chaveAudio();
  o.textContent = velha ? `${txt} — DESATUALIZADA, gere de novo` : txt;
  o.className = "selo " + (velha ? "pend" : "ok");
}

async function renderAudio() {
  if (!P) return;
  renderTimelineAudio(); renderResumoAudio(); renderMix(); renderOuvindo();
  if (!$("[data-painel=audio]").hidden) renderPainelTrilha();
}
async function abrirAbaAudio() {
  await Promise.all([carregarBiblio("musicas"), carregarBiblio("efeitos")]);
  renderAudio();
}

// salva uma mudanca de audio (parcial por trilha) e redesenha
const salvarAudio = (parcial) => tentar(() => salvarProjeto({ audio: parcial }));

$("#tl-audio").addEventListener("click", (e) => {
  const mute = e.target.dataset.mute, solo = e.target.dataset.solo;
  if (mute) {
    if (mute === "efeitos") { const liga = !trilhaAtiva("efeitos"); return salvarAudio({ efeitos: P.audio.efeitos.map((x) => ({ ...x, ativo: liga })) }); }
    return salvarAudio({ [mute]: { ativo: !P.audio[mute].ativo } });
  }
  if (solo) return previa(solo);
  const linha = e.target.closest(".tl-linha"); if (!linha) return;
  trilhaSel = linha.dataset.trilha;
  const pista = e.target.closest(".tl-pista");
  if (pista) {
    const r = pista.getBoundingClientRect();
    cursorT = Math.max(0, Math.min(P.duracao, ((e.clientX - r.left) / r.width) * P.duracao));
    const a = $("#audio-previa"); if (a.src && previaChave) a.currentTime = cursorT;
  }
  renderTimelineAudio(); renderPainelTrilha();
});
$("#audio-previa").addEventListener("timeupdate", () => {
  cursorT = $("#audio-previa").currentTime;
  const c = $("#tl-cursor"); if (c) c.style.left = `calc(150px + (100% - 150px) * ${cursorT / Math.max(P.duracao, 0.01)})`;
});

// painel: qualquer campo data-a="trilha.chave" salva sozinho
$("#painel-trilha").addEventListener("input", (e) => {
  if (e.target.type === "range") { const b = e.target.parentElement.querySelector("b"); if (b) b.textContent = fmtDb(+e.target.value); }
});
$("#painel-trilha").addEventListener("change", (e) => tentar(async () => {
  const t = e.target;
  if (t.dataset.a) {
    const [trilha, chave] = t.dataset.a.split(".");
    let v = t.type === "checkbox" ? t.checked : t.value;
    if (t.type === "number" || t.type === "range") v = v === "" ? null : +v;
    if (chave === "arquivo") v = v || null;
    return salvarProjeto({ audio: { [trilha]: { [chave]: v } } });
  }
  if (t.dataset.segI != null) {
    const segs = structuredClone(P.segmentos), s = segs[+t.dataset.segI];
    s.audio = { modo: "padrao", db: 0, ...(s.audio || {}) };
    s.audio[t.dataset.segK] = t.dataset.segK === "db" ? +t.value : t.value;
    return salvarProjeto({ segmentos: segs });
  }
  if (t.dataset.fxI != null) {
    const fx = structuredClone(P.audio.efeitos), k = t.dataset.fxK;
    fx[+t.dataset.fxI][k] = t.type === "checkbox" ? t.checked : k === "arquivo" ? (t.value || null) : t.value === "" ? null : +t.value;
    return salvarProjeto({ audio: { efeitos: fx } });
  }
}));
$("#painel-trilha").addEventListener("click", (e) => tentar(async () => {
  const d = e.target.dataset;
  if (e.target.id === "fx-add") {
    if (!biblio.efeitos.length) throw new Error("coloque primeiro um som na biblioteca de efeitos (abaixo)");
    return salvarProjeto({ audio: { efeitos: [...P.audio.efeitos, { arquivo: biblio.efeitos[0].nome, em: +cursorT.toFixed(2) }] } });
  }
  if (d.fxDel != null) return salvarProjeto({ audio: { efeitos: P.audio.efeitos.filter((_, i) => i !== +d.fxDel) } });
  if (d.fxCursor != null) { const fx = structuredClone(P.audio.efeitos); fx[+d.fxCursor].em = +cursorT.toFixed(2); return salvarProjeto({ audio: { efeitos: fx } }); }
  if (d.cursorPara) { const [tr, k] = d.cursorPara.split("."); return salvarProjeto({ audio: { [tr]: { [k]: +cursorT.toFixed(2) } } }); }
  if (d.enviar) {
    const f = $(`[data-up="${d.enviar}"]`).files[0]; if (!f) throw new Error("escolha um arquivo de áudio");
    const fd = new FormData(); fd.append("arquivo", f, f.name);
    const m = await api("POST", `/api/biblioteca/${d.enviar}/upload`, fd);
    await depoisBiblio(d.enviar, m);
  }
  if (d.baixar) {
    const t = await api("POST", `/api/biblioteca/${d.baixar}/url`, { url: $(`[data-url="${d.baixar}"]`).value });
    await depoisBiblio(d.baixar, await acompanhar(t, `#tarefa-biblio-${d.baixar}`));
  }
  if (d.removerBiblio) {
    if (!confirm(`Excluir "${d.nome}" da biblioteca? Isso apaga o arquivo da pasta ${d.removerBiblio}/.`)) return;
    await api("DELETE", `/api/biblioteca/${d.removerBiblio}/${encodeURIComponent(d.nome)}`);
    await carregarBiblio(d.removerBiblio); renderAudio();
  }
  if (e.target.id === "narr-import-ok") {
    const f = $("#narr-import").files[0]; if (!f) throw new Error("escolha um arquivo de áudio");
    const fd = new FormData(); fd.append("arquivo", f, f.name);
    const r = await api("POST", `${base()}/narracao`, fd); analiseNarr = null; P = r; renderTudo();
    if (r.analise && r.analise.avisos.length) aviso("Narração importada, mas: " + r.analise.avisos.join(" "), true); else aviso("Narração importada.");
  }
}));
async function depoisBiblio(tipo, m) {
  await carregarBiblio(tipo);
  if (tipo === "musicas") await salvarProjeto({ audio: { musica: { arquivo: m.nome } } });
  else renderAudio();
  aviso(`"${m.nome}" adicionado à biblioteca.`);
}
$$("[data-mix]").forEach((i) => i.addEventListener("change", () =>
  salvarAudio({ mix: { [i.dataset.mix]: i.type === "checkbox" ? i.checked : i.value } })));

async function previa(solo = null) {
  return tentar(async () => {
    const chave = chaveAudio();
    const r = await acompanhar(await api("POST", `${base()}/audio/previa`, { solo }), "#tarefa-audio");
    previaChave = chave; previaSolo = solo; renderOuvindo();
    const a = $("#audio-previa"); a.src = arq(r.arquivo); a.currentTime = 0; a.play().catch(() => {});
  });
}
$("#previa-audio").onclick = () => previa(null);
