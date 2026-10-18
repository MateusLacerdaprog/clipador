// Clipador - lista de projetos, guia do formato, etapas/proximo passo e abas.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------------- projetos
let CATALOGO = null;                          // formatos disponiveis por tipo (curto/longo)
const nomeFormato = (tipo, id) => ((CATALOGO?.[tipo] || []).find((f) => f.id === (id || "livre")) || {});

async function carregarLista() {
  const lista = await api("GET", "/api/projetos");
  for (const ul of $$(".lista-projetos")) {
    const itens = lista.filter((p) => (p.tipo || "curto") === ul.dataset.tipo);
    ul.innerHTML = itens.map((p) => {
      const f = nomeFormato(p.tipo, p.formato);
      const ativo = P && P.nome === p.nome;
      return `<li class="${ativo ? "ativo" : ""}"><button type="button" data-n="${esc(p.nome)}" ${ativo ? 'aria-current="true"' : ""} title="${esc(f.nome || "")}">
        <span class="ic" aria-hidden="true">${f.icone || "•"}</span>${esc(p.nome)}</button></li>`;
    }).join("") || `<li class="vazio-lista">nenhum ainda</li>`;
  }
}
for (const ul of $$(".lista-projetos")) {
  ul.onclick = (e) => { const b = e.target.closest("[data-n]"); if (b) abrirProjeto(b.dataset.n); };
}

// novo projeto: escolhe o tipo (botao da area) e o formato (cartoes)
let novoTipo = "curto";
$$("[data-novo]").forEach((b) => (b.onclick = () => abrirNovo(b.dataset.novo)));
function abrirNovo(tipo) {
  novoTipo = tipo;
  $("#dlg-titulo").textContent = tipo === "longo" ? "Novo vídeo longo (YouTube 16:9)" : "Novo vídeo curto (Shorts · TikTok · Reels)";
  $("#grade-formatos").innerHTML = CATALOGO[tipo].map((f, i) => `
    <label class="formato-card"><input type="radio" name="formato" value="${f.id}" ${i === 0 ? "checked" : ""}>
      <b>${f.icone} ${esc(f.nome)}</b><span>${esc(f.descricao)}</span>
      ${f.evidencias.length ? `<small>📊 ${esc(f.evidencias[0])}</small>` : ""}
      ${f.duracao_alvo ? `<small>⏱ alvo: ${f.duracao_alvo >= 120 ? Math.round(f.duracao_alvo / 60) + " min" : f.duracao_alvo + " s"}</small>` : ""}
    </label>`).join("");
  $("#novo-nome").value = "";
  carregarKits().then(() => { $("#novo-kit").innerHTML = `<option value="">nenhum</option>` + KITS.kits.map((k) => `<option value="${esc(k.id)}">${esc(k.nome)}</option>`).join(""); }).catch(() => {});
  $("#dlg-novo").showModal();
  $("#novo-nome").focus();
}
$("#form-novo").addEventListener("submit", (e) => {
  if (e.submitter && e.submitter.value === "cancelar") return;
  e.preventDefault();
  tentar(async () => {
    const formato = $('#grade-formatos input:checked')?.value || "livre";
    const p = await api("POST", "/api/projetos", { nome: $("#novo-nome").value, tipo: novoTipo, formato: formato === "livre" ? null : formato,
      kit: $("#novo-kit").value || null });
    $("#dlg-novo").close();
    await abrirProjeto(p.nome);
    $("#guia-formato").open = !!p.formato;
    aviso("Projeto criado com o preset do formato. Comece adicionando o vídeo (aba 1).");
  });
});

async function abrirProjeto(nome) {
  P = await api("GET", `/api/projetos/${encodeURIComponent(nome)}`);
  localStorage.setItem("clipador.projeto", nome);
  segSel = -1;
  historico.antes = []; historico.depois = []; atualizarBotoesHistorico();
  $("#vazio").hidden = true; $("#editor").hidden = false;
  await Promise.all([carregarLista(), carregarKits().catch(() => {})]);
  TXT = null; selTxt = null; saidaSel = null; habilitarDerivados(null); $("#det-texto").open = false;
  renderTudo();
  renderGuia();
}

$("#duplicar-projeto").onclick = () => tentar(async () => {
  const origem = P.nome;
  const novo = await api("POST", `${base()}/duplicar`, {});
  await abrirProjeto(novo.nome);
  aviso(`Cópia “${novo.nome}” aberta: mude o gancho (aba 6) e compare com “${origem}”.`, false,
    { rotulo: `Voltar a ${origem}`, fn: () => tentar(() => abrirProjeto(origem)) });
});

// ------------------------------------------------------------- guia do formato
async function renderGuia() {
  const g = await api("GET", `${base()}/guia`);
  SUGESTAO_GANCHO = g.sugestao_gancho || ""; renderTextos();
  const tipoTxt = P.tipo === "longo" ? "Vídeo longo" : "Vídeo curto";
  $("#guia-titulo").textContent = `${g.icone} ${tipoTxt} · ${g.nome}`;
  if (!g.estrutura.length) { $("#guia-corpo").innerHTML = `<p class="dica">Formato livre: sem estrutura sugerida. Escolha um formato na aba Estilo para receber o guia.</p>`; return; }
  const alvo = g.duracao_alvo, fmtT = (s) => (alvo >= 120 ? mmss(s).replace(/\.\d$/, "") : s.toFixed(0) + " s");
  const atual = P.duracao;
  $("#guia-corpo").innerHTML = `
    <p>${esc(g.descricao)}</p>
    <div class="estrutura">${g.estrutura.map((b) => `<div style="flex:${Math.max(b.fim - b.ini, 0.01)} 1 150px" title="${esc(b.dica)}"><b>${esc(b.nome)}</b><small>${fmtT(b.ini)}–${fmtT(b.fim)}</small><span>${esc(b.dica)}</span></div>`).join("")}</div>
    <p class="dica">Duração-alvo: ${fmtT(alvo)} · sua timeline agora: ${fmtT(atual)}${atual > alvo * 1.4 ? " — <b>bem acima do alvo</b>" : atual && atual < alvo * 0.5 ? " — abaixo do alvo" : ""}${g.max_cena ? ` · cenas de até ~${g.max_cena} s` : ""}</p>
    <div class="duas-colunas">
      <div><h4>Checklist</h4><ul>${g.checklist.map((c) => `<li>${esc(c)}</li>`).join("")}</ul></div>
      <div><h4>O que a pesquisa observou</h4><ul>${g.evidencias.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>
        <p class="dica">Dados de vídeos públicos (out/2026). Servem de referência, não são garantia de views.</p></div>
    </div>
    <div class="linha"><button id="usar-roteiro">Colocar o roteiro-modelo na aba Narração</button></div>`;
  $("#usar-roteiro").onclick = () => tentar(async () => {
    if ((P.roteiro || "").trim() && !confirm("Substituir o roteiro atual pelo modelo do formato?")) return;
    await salvarProjeto({ roteiro: g.roteiro }); aviso("Roteiro-modelo colocado na aba 5 · Narração.");
  });
}
async function recarregar() { P = await api("GET", base()); renderTudo(); }
// toda edicao e salva na hora (salvamento automatico) e entra no historico de desfazer
async function salvarProjeto(parcial) {
  const antes = fotografia();
  P = await api("PUT", base(), parcial);
  historico.antes.push(antes); historico.antes.splice(0, historico.antes.length - 80); historico.depois = [];
  atualizarBotoesHistorico(); renderTudo();
  const s = $("#salvo"); s.textContent = "✓ salvo"; clearTimeout(s.t); s.t = setTimeout(() => (s.textContent = ""), 1800);
}

function renderTudo() {
  $("#titulo-projeto").textContent = P.nome;
  const longo = P.tipo === "longo";
  $("#resumo").textContent = `${longo ? "longo 16:9" : "curto 9:16"} · ${P.segmentos.length} trechos · ${longo ? mmss(P.duracao) : P.duracao.toFixed(1) + " s"}` +
    (longo ? "" : ` · layout ${P.layout.replace("_", " ")}`) + (P.narracao ? ` · narração ${P.narracao_dur.toFixed(1)} s` : " · sem narração") +
    (P.arquivos_faltando?.length ? ` · ⚠ ${P.arquivos_faltando.length} arquivo(s) faltando` : "");
  renderFontes(); renderCortes(); renderEstilo(); renderAudio(); renderNarracao(); renderRevisar(); renderPublicacao(); renderAlertaLegenda(); if (typeof renderReact === 'function') renderReact();
  atualizarEtapas();
}

// ------------------------------------------------- etapas e "proximo passo"
const TXT_ESTADO = { ok: "feito", pend: "pendente" };
function estadoEtapas() {
  return {
    fonte: P.fontes.length ? "ok" : "pend",
    cortes: P.segmentos.length ? "ok" : P.fontes.length ? "pend" : "",
    narracao: P.narracao ? "ok" : "",
    legendas: P.n_cartoes ? "ok" : "",
    revisar: P.aprovado_atual ? "ok" : P.rascunho_atual ? "pend" : "",
  };
}
function atualizarEtapas() {
  const est = estadoEtapas();
  $$("#abas button[data-aba]").forEach((b) => {
    const marca = b.querySelector(".etapa-estado"); if (!marca) return;      // Assistente e React (extras) nao tem estado
    const s = est[b.dataset.aba] || "";
    b.dataset.estado = s;
    marca.textContent = s === "ok" ? "✓" : s === "pend" ? "•" : "";
    b.querySelector(".so-leitor").textContent = s ? `, ${TXT_ESTADO[s]}` : "";
  });
  renderProximo();
}
function proximoPasso() {
  if (!P.fontes.length) return { texto: "comece adicionando o vídeo do jogo.", aba: "fonte", rotulo: "Ir para 1 · Fonte" };
  if (!P.segmentos.length) return { texto: "escolha os trechos do vídeo: clique nas cenas ou use os momentos automáticos.", aba: "cortes", rotulo: "Ir para 2 · Cortes" };
  if (!P.narracao && !P.n_cartoes) return { texto: "opcional: grave a sua narração (ela vira a legenda). Em vídeo sem voz, siga direto para conferir o resultado.", aba: "narracao", rotulo: "Ir para 5 · Narração" };
  if (P.narracao && !P.n_cartoes) return { texto: "transcreva a narração para gerar as legendas.", aba: "legendas", rotulo: "Ir para 6 · Textos" };
  if (P.n_cartoes && P.legendas_desatualizadas) return { texto: "o vídeo mudou depois das legendas: clique em “Atualizar legendas” para refazê-las.", aba: "legendas", rotulo: "Ir para 6 · Textos" };
  if (!P.rascunho_atual) return { texto: "gere os quadros e um RASCUNHO para conferir como ficou.", aba: "revisar", rotulo: "Ir para 7 · Revisar" };
  if (!P.aprovado_atual) return { texto: "assista ao rascunho inteiro e, se estiver bom, aprove.", aba: "revisar", rotulo: "Ir para 7 · Revisar" };
  return { texto: "você aprovou este rascunho. Gere o vídeo FINAL quando quiser.", aba: "revisar", rotulo: "Ir para 7 · Revisar" };
}
function renderProximo() {
  const p = proximoPasso(), txt = "Próximo passo: " + p.texto, b = $("#proximo-ir");
  if ($("#proximo-texto").textContent !== txt) $("#proximo-texto").textContent = txt;   // so muda o texto quando muda (evita reanunciar)
  b.textContent = p.rotulo; b.dataset.aba = p.aba;
  b.hidden = $("#abas .ativa")?.dataset.aba === p.aba;                                  // ja esta nessa etapa
}
const irParaAba = (aba) => $(`#abas [data-aba="${aba}"]`)?.click();
$("#proximo-ir").onclick = (e) => irParaAba(e.currentTarget.dataset.aba);

// ----------------------------------------------------------------------- abas
$("#abas").onclick = (e) => {
  const b = e.target.closest("button"); if (!b) return;
  $$("#abas button").forEach((x) => {
    x.classList.toggle("ativa", x === b);
    if (x === b) x.setAttribute("aria-current", "step"); else x.removeAttribute("aria-current");
  });
  renderProximo();
  $$("[data-painel]").forEach((s) => (s.hidden = s.dataset.painel !== b.dataset.aba));
  if (b.dataset.aba === "legendas") { carregarCartoes(); tentar(renderPlataformas); tentar(prepararPreviaLegenda); }
  else $("#leg-video")?.pause();
  if (b.dataset.aba === "audio") abrirAbaAudio();
  if (b.dataset.aba === "assistente") tentar(abrirAssistente);
  if (b.dataset.aba === "react") { renderStageReact.forcar = true; renderReact(); tentar(listarDispositivos); }
  else if (typeof pararCamera === "function" && b.dataset.aba !== "react") pararCamera();
};
