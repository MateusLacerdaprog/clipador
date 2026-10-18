// Clipador - centro de comando (interpretar -> executar).
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ================================================================= COMMAND CENTER
// interpretar (servidor, regras ou IA) -> plano visivel -> executar passo a passo (servidor valida cada acao)
const ctxComando = () => ({ trecho: segSel >= 0 ? segSel : null, fonte: $("#cortes-fonte")?.value || null });
let PLANO = null;
function textoParams(a) {
  const p = a.params || {}, partes = [];
  if (p.origem && p.origem !== "auto") partes.push(p.origem === "video" ? "do áudio do vídeo" : "da narração");
  if (p.preset) partes.push(`“${ZOOM?.presets?.[p.preset]?.nome || p.preset}”`);
  if (p.alvo) partes.push(p.alvo === "todos" ? "em todos os trechos" : segSel >= 0 ? `no trecho ${segSel + 1}` : "no trecho selecionado");
  if (p.duracao) partes.push(`clipes de ${p.duracao} s`);
  if (p.quantidade) partes.push(`${p.quantidade} momentos`);
  if (p.plataforma) partes.push(p.plataforma);
  if (p.aba) partes.push(p.aba);
  return partes.length ? ` <span class="dica">(${esc(partes.join(", "))})</span>` : "";
}
function renderItens(itens, el) {
  const ic = { erro: "❌", aviso: "⚠️", dica: "💡", ok: "✅" };
  el.innerHTML = (itens || []).map((i) => `<li class="${i.nivel}"><span aria-hidden="true">${ic[i.nivel]}</span> <b>${esc(i.titulo)}</b>`
    + `<span class="so-leitor">(${i.nivel})</span>${i.detalhe ? ` <span class="dica">${esc(i.detalhe)}</span>` : ""}`
    + `${i.como_resolver ? `<div class="dica">→ ${esc(i.como_resolver)}</div>` : ""}</li>`).join("");
}
function renderPlano() {
  const r = PLANO, el = $("#cc-plano"); el.hidden = false;
  if (!r.plano.length) {
    el.innerHTML = `<p>${esc(r.resposta || "Não entendi.")}</p>` + (r.recusadas?.length ? `<p class="dica">A IA sugeriu ações que não existem (recusadas): ${esc(r.recusadas.join("; "))}</p>` : "")
      + `<div class="mom-motivos">${(r.exemplos || []).map((x) => `<button type="button" class="chip" data-exemplo="${esc(x)}">${esc(x)}</button>`).join("")}</div>`
      + `<div class="linha"><button type="button" class="mini" data-cc-fechar>Fechar</button></div>`;
    return;
  }
  el.innerHTML = `<p class="dica">Entendido por ${esc(r.origem)}${r.resposta ? " · " + esc(r.resposta) : ""}. Vou fazer:</p>
    <ol class="cc-passos">${r.plano.map((a, k) => `<li>${esc(a.desc)}${textoParams(a)}${a.sobrescreve ? ` <span class="chip alerta">⚠ substitui ${esc(a.sobrescreve)}</span>` : ""}`
      + `${a.demorada ? ` <span class="chip">demora</span>` : ""}${a.porque ? ` <span class="dica">— ${esc(a.porque)}</span>` : ""} <span class="cc-estado" id="cc-e${k}"></span></li>`).join("")}</ol>
    <div class="linha"><button type="button" class="primario" data-cc-executar>Executar</button><button type="button" data-cc-fechar>Cancelar</button></div>
    <div id="cc-tarefa" class="tarefa"></div><ul id="cc-resultado" class="verif"></ul>`;
}
$("#cc-form").onsubmit = (e) => { e.preventDefault(); tentar(async () => {
  const texto = $("#cc-texto").value.trim(); if (!texto) throw new Error("escreva o que quer fazer");
  if (!P) throw new Error("abra ou crie um projeto primeiro");
  let r = await api("POST", `${base()}/comando/interpretar`, { texto, usar_ia: $("#cc-ia").checked, contexto: ctxComando() });
  if (r.tarefa) { $("#cc-plano").hidden = false; $("#cc-plano").innerHTML = `<div id="cc-tarefa" class="tarefa"></div>`; r = await acompanhar(r.tarefa, "#cc-tarefa"); }
  PLANO = r; renderPlano();
}); };
$("#cc-plano").onclick = (e) => tentar(async () => {
  if (e.target.dataset.exemplo) { $("#cc-texto").value = e.target.dataset.exemplo; $("#cc-form").requestSubmit(); return; }
  if (e.target.closest("[data-cc-fechar]")) { $("#cc-plano").hidden = true; PLANO = null; return; }
  if (!e.target.closest("[data-cc-executar]")) return;
  e.target.disabled = true;
  let abaFinal = null, itens = [];
  for (const [k, a] of PLANO.plano.entries()) {
    const marca = $(`#cc-e${k}`); marca.textContent = "⏳ fazendo…";
    try {
      const antes = fotografia();
      const r = await api("POST", `${base()}/comando/executar`, { acao: a.acao, params: a.params, contexto: ctxComando() });
      historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
      P = r.estado; renderTudo();
      let res = null;
      if (r.tarefa) { res = await acompanhar(r.tarefa, "#cc-tarefa"); await recarregar(); if (a.acao === "legendas.gerar") await carregarCartoes(); }
      if (r.itens) itens = itens.concat(r.itens);
      if (res?.itens) itens = itens.concat(res.itens);
      if (r.criados) await carregarLista();
      if (r.modo_cortes) modoCortes(r.modo_cortes);
      abaFinal = r.aba || abaFinal;
      marca.textContent = "✓ " + (res?.mensagem || r.mensagem || "feito");
    } catch (err) { marca.textContent = "✗ " + err.message; marca.classList.add("erro"); break; }
  }
  renderItens(itens, $("#cc-resultado"));
  if (abaFinal) irParaAba(abaFinal);
  if (PLANO.plano.some((a) => a.acao === "momentos.achar")) modoCortes("momentos");
});
$("#verificar").onclick = () => tentar(async () => {
  const r = await api("GET", `${base()}/verificar`);
  renderItens(r.itens, $("#lista-verif"));
  aviso(r.conferiu_arquivo ? "Projeto e RASCUNHO atual conferidos." : "Projeto conferido (gere um RASCUNHO para conferir também o arquivo).");
});

$("#zoom-sugerir").onclick = () => tentar(async () => {
  if (!P.segmentos.length) throw new Error("a timeline está vazia");
  const antes = fotografia();
  const r = await api("POST", `${base()}/zoom/sugerir`);
  P = r; historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico(); renderTudo();
  aviso(r.sugeridos.length ? `Zoom de impacto em ${r.sugeridos.length} trecho(s) com pico de ação: ${r.sugeridos.map((x) => `#${x.trecho} em ${x.em_s}s`).join(", ")}.`
    : "Nenhum trecho tem um pico de ação forte o bastante: nada mudou (zoom em tudo cansa).", false, r.sugeridos.length ? { rotulo: "Desfazer", fn: desfazer } : null);
});
$("#foco-auto").onclick = () => tentar(async () => {
  if (!P.segmentos.length) throw new Error("a timeline está vazia");
  const antes = fotografia();
  P = await api("POST", `${base()}/foco_auto`, {});
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); aviso("Foco ajustado para onde está a ação em cada trecho (Ctrl+Z desfaz).");
});
$("#grade-cenas").onclick = (e) => tentar(async () => {
  const d = e.target.closest(".cena"); if (!d) return;
  const f = fonteAtual(), c = f.cenas[+d.dataset.i];
  const v = $("#player-fonte"); v.currentTime = c.ini; v.play();
  if (e.shiftKey || e.target.closest(".cena-ver")) return;
  const fim = Math.min(c.fim, c.ini + 4);  // cena longa: começa com 4 s, ajuste na timeline
  await addSegmento({ fonte: f.id, ini: c.ini, fim });
});
$("#marcar-ini").onclick = () => { marca.ini = $("#player-fonte").currentTime; mostrarMarca(); };
$("#marcar-fim").onclick = () => { marca.fim = $("#player-fonte").currentTime; mostrarMarca(); };
function mostrarMarca() { $("#marcacao").textContent = `${marca.ini == null ? "--" : mmss(marca.ini)} → ${marca.fim == null ? "--" : mmss(marca.fim)}`; }
$("#add-trecho").onclick = () => tentar(async () => {
  if (marca.ini == null || marca.fim == null || marca.fim <= marca.ini) throw new Error("marque início e fim (fim depois do início)");
  await addSegmento({ fonte: fonteAtual().id, ini: +marca.ini.toFixed(2), fim: +marca.fim.toFixed(2) });
  marca = { ini: null, fim: null }; mostrarMarca();
});
async function addSegmento(s) {
  const segs = [...P.segmentos, { foco_x: 0.5, zoom: 1, ...s }];
  segSel = segs.length - 1;
  await salvarProjeto({ segmentos: segs });
}
$("#sugerir").onclick = () => tentar(async () => {
  const f = fonteAtual(); if (!f) throw new Error("adicione um vídeo primeiro");
  const tinha = P.segmentos.length, antes = fotografia();
  P = await api("POST", `${base()}/fontes/${f.id}/sugerir`, { alvo: +$("#alvo-s").value || 20 });
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); aviso("Cortes sugeridos pelas melhores cenas. Revise e ajuste.", false, tinha ? { rotulo: "Desfazer", fn: desfazer } : null);
});

function renderSegmentos() {
  renderTimelineVideo();
  $("#dur-timeline").textContent = `· ${P.duracao.toFixed(1)} s`;
  const opcFontes = (sel) => P.fontes.map((f) => `<option value="${f.id}" ${f.id === sel ? "selected" : ""}>${esc(f.nome)}</option>`).join("");
  const longo = P.tipo === "longo";
  const comp = !longo && P.layout === "comparacao";
  const comRotulo = longo ? (P.formato_cfg?.capitulos ? "capítulo" : null) : (P.formato_cfg?.ranking ? "texto no ranking" : null);
  $("#lista-segmentos").innerHTML = P.segmentos.map((s, i) => `
    <li data-i="${i}" class="${i === segSel ? "sel" : ""}">
      <div class="linha">
        <b>${(s.fim - s.ini).toFixed(1)} s</b>
        <label>de <input type="number" step="0.1" data-k="ini" value="${s.ini}"></label>
        <label>até <input type="number" step="0.1" data-k="fim" value="${s.fim}"></label>
        <button data-acao="tocar" title="tocar" aria-label="Tocar o trecho ${i + 1}">▶</button>
        <button data-acao="subir" title="mover para cima" aria-label="Mover o trecho ${i + 1} para cima">↑</button>
        <button data-acao="descer" title="mover para baixo" aria-label="Mover o trecho ${i + 1} para baixo">↓</button>
        <button data-acao="remover" title="remover" aria-label="Remover o trecho ${i + 1}">✕</button>
      </div>
      ${!comp ? `<div class="linha">
        ${!longo ? `<label>enquadramento ← → <input type="range" min="0" max="1" step="0.01" data-k="foco_x" value="${s.foco_x ?? 0.5}"></label>` : ""}
      </div>${linhaZoom(s, i)}` : ""}
      ${comRotulo ? `<div class="linha"><label>${comRotulo} <input data-k="rotulo" maxlength="60" value="${esc(s.rotulo || "")}"
        placeholder="${longo ? "deixe vazio se continua o capítulo anterior" : `${P.segmentos.length - i}º lugar`}" class="cresce"></label></div>` : ""}
      ${comp ? `<div class="linha">
        <label>rótulo A <input data-k="rotulo_a" value="${esc(s.rotulo_a || "")}" placeholder="${esc(P.comparacao?.rotulo_a || "GTA 5")}" style="width:90px"></label>
        <label>vídeo de baixo (B) <select data-k="fonte_b">${opcFontes(s.fonte_b || P.comparacao?.fonte_b || s.fonte)}</select></label>
        <label title="Instante do vídeo B que aparece junto com o início deste trecho (alinhe a mesma cena)">B começa em <input type="number" step="0.1" min="0" data-k="ini_b" value="${s.ini_b ?? s.ini}"> s</label>
        <label>rótulo B <input data-k="rotulo_b" value="${esc(s.rotulo_b || "")}" placeholder="${esc(P.comparacao?.rotulo_b || "GTA 6")}" style="width:90px"></label>
      </div>
      <div class="linha">
        <label title="Qual parte do vídeo de cima aparece">enquadrar A ← → <input type="range" min="0" max="1" step="0.01" data-k="foco_x" value="${s.foco_x ?? 0.5}"></label>
        <label title="Qual parte do vídeo de baixo aparece">enquadrar B ← → <input type="range" min="0" max="1" step="0.01" data-k="foco_x_b" value="${s.foco_x_b ?? s.foco_x ?? 0.5}"></label>
        <button class="mini" data-acao="previa-trecho" aria-label="Prévia exata do trecho ${i + 1} com A e B">▶ Prévia exata</button>
      </div>` : ""}
    </li>`).join("") || `<p class="dica">${P.layout === "comparacao" && P.tipo !== "longo" ? "Sem trechos. Use o Editor A × B acima para cortar os dois vídeos." : "Sem trechos. Clique nas cenas ou use “Sugerir cortes”."}</p>`;
  desenharMoldura(); renderCmpEditor();
}
$("#lista-segmentos").addEventListener("click", (e) => tentar(async () => {
  const li = e.target.closest("li"); if (!li) return;
  const i = +li.dataset.i, segs = [...P.segmentos], s = segs[i];
  const acao = e.target.dataset.acao;
  if (segSel !== i) { segSel = i; $$("#lista-segmentos li").forEach((x) => x.classList.toggle("sel", +x.dataset.i === i)); desenharMoldura(); renderCmpEditor(); }
  if (!acao) return;
  if (acao === "tocar") {
    if ($("#cortes-fonte").value !== s.fonte) { $("#cortes-fonte").value = s.fonte; carregarFonteNoPlayer(); }
    const v = $("#player-fonte"); v.currentTime = s.ini; v.play();
    const parar = () => { if (v.currentTime >= s.fim) { v.pause(); v.removeEventListener("timeupdate", parar); } };
    v.addEventListener("timeupdate", parar); return;
  }
  if (acao === "previa-trecho") {
    const r = await acompanhar(await api("POST", `${base()}/previa_trecho`, { i }), "#tarefa-render-trecho");
    const v = $("#pt-video"); v.src = `${base()}/arquivo?caminho=${encodeURIComponent(r.arquivo)}&v=${r.v}`;
    $("#dlg-previa-trecho").showModal(); v.play().catch(() => {}); return;
  }
  if (acao === "zoom-preset") {
    const nome = prompt("Nome do preset de zoom (ex.: Soco forte):"); if (!nome) return;
    const fx = s.zoom_fx, r = await api("POST", "/api/zoom/presets", { nome, ...Object.fromEntries(VALORES_ZOOM.map((c) => [c, fx[c]])) });
    ZOOM = { presets: r.presets, curvas: r.curvas, embutidos: r.embutidos };
    segs[i] = { ...s, zoom_fx: { ...fx, preset: r.id } };
    await salvarProjeto({ segmentos: segs });
    aviso(`Preset “${r.presets[r.id].nome}” salvo: já aparece no menu Zoom de todos os trechos e na Biblioteca de estilos.`); return;
  }
  if (acao === "remover") segs.splice(i, 1);
  if (acao === "subir" && i > 0) [segs[i - 1], segs[i]] = [segs[i], segs[i - 1]];
  if (acao === "descer" && i < segs.length - 1) [segs[i + 1], segs[i]] = [segs[i], segs[i + 1]];
  segSel = acao === "subir" ? i - 1 : acao === "descer" ? i + 1 : -1;
  await salvarProjeto({ segmentos: segs });
}));
$("#lista-segmentos").addEventListener("input", (e) => {
  const k = e.target.dataset.k; if (k === "foco_x") { P.segmentos[+e.target.closest("li").dataset.i].foco_x = +e.target.value; desenharMoldura(); }
  const z = e.target.dataset.zfx;                     // mexendo no ponto/forca: a moldura do zoom acompanha ao vivo
  if (z && ["foco_x", "foco_y", "intensidade"].includes(z)) {
    const s = P.segmentos[+e.target.closest("li").dataset.i]; if (s.zoom_fx) { s.zoom_fx[z] = +e.target.value; desenharMoldura(); }
    const rot = e.target.closest("label")?.querySelector("b"); if (rot) rot.textContent = z === "intensidade" ? (+e.target.value).toFixed(2) + "×" : Math.round(e.target.value * 100) + "%";
  }
});
