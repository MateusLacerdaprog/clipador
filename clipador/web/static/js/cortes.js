// Clipador - aba 2 Cortes: cenas, trechos e momentos (destaques).
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// -------------------------------------------------------------------- 2 CORTES
const fonteAtual = () => P.fontes.find((f) => f.id === $("#cortes-fonte").value);

function renderCortes() {
  const sel = $("#cortes-fonte"), antes = sel.value;
  sel.innerHTML = P.fontes.map((f) => `<option value="${f.id}">${esc(f.nome)}</option>`).join("");
  if (P.fontes.some((f) => f.id === antes)) sel.value = antes;
  carregarFonteNoPlayer();
  renderSegmentos();
}
$("#cortes-fonte").onchange = carregarFonteNoPlayer;

function carregarFonteNoPlayer() {
  const f = fonteAtual(), v = $("#player-fonte");
  if (!f) { v.removeAttribute("src"); $("#grade-cenas").innerHTML = `<p class="dica">Adicione um vídeo na aba 1.</p>`; return; }
  const url = `${base()}/fontes/${f.id}/video`;
  if (!v.src.endsWith(url)) v.src = url;
  $("#grade-cenas").innerHTML = f.cenas.map((c, i) => {
    const cl = c.nota >= 65 ? "alta" : c.nota >= 50 ? "media" : "baixa";
    const dur = (c.fim - c.ini).toFixed(1);
    return `<div class="cena" data-i="${i}">
      <button type="button" class="cena-add" title="Adicionar à timeline (Shift+clique: só tocar)" aria-label="Adicionar à timeline a cena de ${mmss(c.ini)}, ${dur} segundos, nota ${c.nota}">
        ${c.miniatura ? `<img alt="" loading="lazy" src="${base()}/arquivo?caminho=${encodeURIComponent(c.miniatura)}">` : ""}
        <span class="cena-info"><span>${mmss(c.ini)} · ${dur}s</span><span class="nota ${cl}">${c.nota}</span></span></button>
      <button type="button" class="cena-ver mini" title="Só tocar, sem adicionar" aria-label="Ver a cena de ${mmss(c.ini)} no player">▶</button></div>`;
  }).join("");
  renderMomentos();
}

// ------------------------------------------------------------- momentos (destaques)
function modoCortes(modo) {
  $$("[data-modo]").forEach((b) => { const on = b.dataset.modo === modo; b.classList.toggle("ativo", on); b.setAttribute("aria-pressed", on); });
  $("#modo-cenas").hidden = modo !== "cenas"; $("#modo-momentos").hidden = modo !== "momentos";
}
$(".modos").onclick = (e) => { const b = e.target.closest("[data-modo]"); if (b) modoCortes(b.dataset.modo); };
function renderMomentos() {
  renderPedido();
  const f = fonteAtual(), D = f && f.destaques, lista = (D && D.lista) || [];
  $("#mom-acoes").hidden = !lista.length;
  if (D) $("#mom-dur").value = D.duracao;
  $("#mom-lista").innerHTML = lista.map((m, i) => {
    const cl = m.nota >= 65 ? "alta" : m.nota >= 50 ? "media" : "baixa";
    return `<li data-i="${i}">
      <div class="linha"><label><input type="checkbox" class="mom-marca" aria-label="Marcar o momento de ${mmss(m.ini)} a ${mmss(m.fim)}" ${i < 3 ? "checked" : ""}></label>
        <b>${mmss(m.ini)} → ${mmss(m.fim)}</b>${m.nota == null ? `<span class="nota media" title="sugestão da IA, sem nota medida">IA</span>` : `<span class="nota ${cl}">${m.nota}</span>`}
        <button class="mini" data-ver="${i}">▶ Ver</button><button class="mini" data-pico="${i}">▶ Pico ${mmss(m.pico)}</button>
        <button class="mini" data-usar="${i}">Usar na timeline</button></div>
      <div class="mom-motivos">${m.motivos.map((t) => `<span class="chip ok">✓ ${esc(t)}</span>`).join("")}${(m.alertas || []).map((t) => `<span class="chip alerta">⚠ ${esc(t)}</span>`).join("")}</div>
    </li>`;
  }).join("") || `<p class="dica">${f ? "Clique em “Achar momentos”: o Clipador procura os trechos com mais ação e explica a nota." : ""}</p>`;
}
$("#mom-analisar").onclick = () => tentar(async () => {
  const f = fonteAtual(); if (!f) throw new Error("adicione um vídeo primeiro");
  const t = await api("POST", `${base()}/fontes/${f.id}/destaques`, { duracao: +$("#mom-dur").value || 25, quantidade: +$("#mom-qtd").value || 5 });
  await acompanhar(t, "#mom-tarefa");
  $("#mom-tarefa").textContent = "";
  P = await api("GET", base()); renderTudo();
  aviso("Momentos encontrados. A nota compara trechos deste vídeo entre si; não prevê visualizações.");
});
$("#mom-lista").onclick = (e) => tentar(async () => {
  const b = e.target.closest("button"); if (!b) return;
  const f = fonteAtual(), lista = f.destaques.lista, v = $("#player-fonte");
  if (b.dataset.ver) { v.currentTime = lista[+b.dataset.ver].ini; v.play(); return; }
  if (b.dataset.pico) { v.currentTime = Math.max(0, lista[+b.dataset.pico].pico - 1); v.play(); return; }
  if (b.dataset.usar) {
    const tinha = P.segmentos.length, antes = fotografia();
    P = await api("POST", `${base()}/fontes/${f.id}/destaques/aplicar`, { indice: +b.dataset.usar });
    historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
    renderTudo();
    aviso(tinha ? "Timeline substituída por este momento (dividido nos cortes, com foco automático)." : "Momento na timeline, dividido nos cortes de cena e com foco automático. Ajuste à vontade.",
      false, tinha ? { rotulo: "Desfazer", fn: desfazer } : null);
  }
});
$("#mom-lote").onclick = () => tentar(async () => {
  const f = fonteAtual();
  const idx = [...document.querySelectorAll("#mom-lista li")].filter((li) => li.querySelector(".mom-marca").checked).map((li) => +li.dataset.i);
  if (!idx.length) throw new Error("marque pelo menos um momento");
  if (!confirm(`Criar ${idx.length} projeto(s) novo(s), um por momento?`)) return;
  const r = await api("POST", `${base()}/fontes/${f.id}/destaques/lote`, { indices: idx });
  await carregarLista();
  aviso(`Criados: ${r.criados.join(", ")} (na lista de projetos à esquerda).`);
});
// clipar por pedido: busca local na fala ou IA (so texto)
function renderPedido() {
  const f = fonteAtual(), D = f && f.destaques;
  $("#ped-info").textContent = !f ? "" : D && D.pedido
    ? `Pedido: “${D.pedido}” · ${D.origem || ""}${D.observacao ? " · IA: " + D.observacao : ""}${D.lista.length ? "" : " · nada encontrado"}`
    : (f.info.audio ? "Para buscar na fala, transcreva o vídeo uma vez (Whisper roda no seu PC)." : "Vídeo sem áudio: o pedido só pode usar os momentos medidos (Pedir à IA).");
}
async function transcreverFonte() {
  const f = fonteAtual(); if (!f) throw new Error("adicione um vídeo primeiro");
  await acompanhar(await api("POST", `${base()}/fontes/${f.id}/transcrever`), "#mom-tarefa");
  $("#mom-tarefa").textContent = "";
}
$("#ped-transcrever").onclick = () => tentar(async () => { await transcreverFonte(); aviso("Fala transcrita. Agora é só buscar."); });
const corpoPedido = (modo) => ({ texto: $("#ped-texto").value, duracao: +$("#mom-dur").value || 25, quantidade: +$("#mom-qtd").value || 5, modo });
$("#ped-local").onclick = () => tentar(async () => {
  const f = fonteAtual(); if (!f) throw new Error("adicione um vídeo primeiro");
  if (!$("#ped-texto").value.trim()) throw new Error("escreva o que procurar");
  const t = await api("GET", `${base()}/fontes/${f.id}/transcricao`);
  if (!t.palavras) {
    if (!f.info.audio) throw new Error("este vídeo não tem áudio: use “Pedir à IA” ou “Achar momentos”");
    if (!confirm("A fala deste vídeo ainda não foi transcrita. Transcrever agora? (local; vídeos longos demoram)")) return;
    await transcreverFonte();
  }
  const r = await api("POST", `${base()}/fontes/${f.id}/pedido`, corpoPedido("local"));
  P = r; renderTudo();
  aviso(r.encontrados ? `${r.encontrados} trecho(s) onde isso é falado.` : "Não achei isso na fala. Tente outras palavras ou “Pedir à IA”.", !r.encontrados);
});
$("#ped-ia").onclick = () => tentar(async () => {
  const f = fonteAtual(); if (!f) throw new Error("adicione um vídeo primeiro");
  if (!$("#ped-texto").value.trim()) throw new Error("escreva o que procurar");
  const pv = await api("POST", `${base()}/fontes/${f.id}/pedido/previa`, corpoPedido("ia"));
  if (!pv.provedor) throw new Error("nenhum provedor de IA ativo: configure na aba Assistente (a busca na fala funciona sem IA)");
  if (!confirm(`Enviar ${pv.caracteres} caracteres de TEXTO (transcrição + momentos medidos) para ${pv.provedor}? Nenhum vídeo ou áudio é enviado.\n\nInício do texto:\n${pv.prompt.slice(0, 600)}…`)) return;
  const t = await api("POST", `${base()}/fontes/${f.id}/pedido`, corpoPedido("ia"));
  const fim = await acompanhar(t, "#mom-tarefa");
  $("#mom-tarefa").textContent = "";
  P = await api("GET", base()); renderTudo();
  aviso(`A IA sugeriu ${fim?.quantidade ?? 0} trecho(s). Confira com ▶ Ver antes de usar.`);
});

// editar pelo texto: palavras faladas dentro de cada trecho da timeline
let TXT = null, selTxt = null;
async function carregarTextoMontagem() {
  TXT = await api("GET", `${base()}/transcricao_timeline`); selTxt = null;
  const algum = TXT.trechos.some((t) => t.transcrita);
  $("#texto-montagem").innerHTML = !TXT.trechos.length ? `<p class="dica">Timeline vazia.</p>` : !algum
    ? `<p class="dica">A fala do vídeo-fonte ainda não foi transcrita: use “Transcrever fala” no cartão Momentos.</p>`
    : TXT.trechos.map((t) => `<p><b class="dica">${t.i + 1}.</b> ${t.palavras.length ? t.palavras.map((w, k) =>
        `<span class="pal" data-t="${t.i}" data-k="${k}" title="${w.start.toFixed(2)} s">${esc(w.w)}</span>`).join(" ") : `<span class="dica">(sem fala)</span>`}</p>`).join("");
  mostrarSelTxt();
}
function mostrarSelTxt() {
  document.querySelectorAll("#texto-montagem .pal").forEach((el) => {
    const t = +el.dataset.t, k = +el.dataset.k;
    el.classList.toggle("sel", !!selTxt && t === selTxt.t && k >= Math.min(selTxt.a, selTxt.b) && k <= Math.max(selTxt.a, selTxt.b));
  });
  $("#cortar-texto").disabled = !selTxt;
  if (!selTxt) { $("#sel-texto").textContent = ""; return; }
  const pal = TXT.trechos[selTxt.t].palavras, a = Math.min(selTxt.a, selTxt.b), b = Math.max(selTxt.a, selTxt.b);
  $("#sel-texto").textContent = `${b - a + 1} palavra(s) · ${(pal[b].end - pal[a].start).toFixed(2)} s`;
}
$("#det-texto").addEventListener("toggle", () => { if ($("#det-texto").open) tentar(carregarTextoMontagem); });
$("#texto-montagem").onclick = (e) => {
  const el = e.target.closest(".pal"); if (!el) return;
  const t = +el.dataset.t, k = +el.dataset.k;
  if (e.shiftKey && selTxt && selTxt.t === t) selTxt.b = k; else selTxt = { t, a: k, b: k };
  const w = TXT.trechos[t].palavras[k], v = $("#player-fonte");
  if (!e.shiftKey && v) { v.currentTime = w.start; }
  mostrarSelTxt();
};
// assistente de ritmo: lista as pausas longas; cada corte e uma decisao do usuario (silencio tambem cria expectativa)
let PAUSAS = [];
async function acharPausas() {
  const r = await api("GET", `${base()}/ritmo`);
  PAUSAS = r.sugestoes;
  $("#pausas-resumo").textContent = !r.transcrito ? "Transcreva a fala do vídeo-fonte primeiro (cartão Momentos → Transcrever fala)."
    : PAUSAS.length ? `${PAUSAS.length} pausa(s); cortar as sem aviso economiza ${r.economia_s} s.` : "Nenhuma pausa longa: o ritmo da fala está bom.";
  $("#lista-pausas").innerHTML = PAUSAS.map((s, k) => `<li class="${s.talvez_manter ? "aviso" : ""}">`
    + `<b>${s.pausa_s.toFixed(1)} s</b> de pausa em ${mmss(s.na_montagem_s)} (trecho ${s.trecho + 1}) — entre “${esc(s.depois_de)}” e “${esc(s.antes_de)}”`
    + `${s.talvez_manter ? `<div class="dica">⚠ talvez manter: ${esc(s.talvez_manter)}</div>` : ""}`
    + ` <button class="mini" data-pausa="${k}">Cortar esta pausa</button></li>`).join("");
}
$("#achar-pausas").onclick = () => tentar(acharPausas);
$("#lista-pausas").onclick = (e) => tentar(async () => {
  const k = e.target.dataset.pausa; if (k == null) return;
  const s = PAUSAS[+k], antes = fotografia();
  P = await api("POST", `${base()}/timeline`, { op: "cortar_intervalo", i: s.trecho, ini: s.ini, fim: s.fim });
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); await carregarTextoMontagem(); await acharPausas();
  aviso("Pausa cortada (Ctrl+Z desfaz).");
});
$("#cortar-texto").onclick = () => tentar(async () => {
  const tr = TXT.trechos[selTxt.t], pal = tr.palavras, a = Math.min(selTxt.a, selTxt.b), b = Math.max(selTxt.a, selTxt.b);
  // corta do inicio da 1a palavra ate o comeco da proxima (sem comer a palavra seguinte) ou o fim do trecho
  const ini = pal[a].start, fim = b + 1 < pal.length ? pal[b + 1].start : Math.min(tr.fim, pal[b].end + 0.15);
  const antes = fotografia();
  P = await api("POST", `${base()}/timeline`, { op: "cortar_intervalo", i: tr.i, ini, fim });
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); await carregarTextoMontagem();
  aviso("Pedaço cortado da montagem (Ctrl+Z desfaz).");
});

// kit do canal + logo
let KITS = { kits: [], logos: [] };
async function carregarKits() { KITS = await api("GET", "/api/kits"); }
function renderKit() {
  if (!P) return;
  const sel = $("#kit-sel").value;
  $("#kit-sel").innerHTML = KITS.kits.length ? KITS.kits.map((k) => `<option value="${esc(k.id)}">${esc(k.nome)}</option>`).join("") : `<option value="">(nenhum kit salvo)</option>`;
  if (sel) $("#kit-sel").value = sel;
  const M = P.marca || {};
  $("#marca-arquivo").innerHTML = `<option value="">sem logo</option>` + KITS.logos.map((l) => `<option ${l === M.arquivo ? "selected" : ""}>${esc(l)}</option>`).join("");
  $("#marca-pos").value = M.pos || "sup_dir"; $("#marca-tamanho").value = M.tamanho ?? 0.14; $("#marca-opacidade").value = M.opacidade ?? 0.85;
  const k = KITS.kits.find((x) => x.id === $("#kit-sel").value), z = k && nomeZoom(k.zoom_padrao);
  $("#kit-zoom").disabled = !z;
  $("#kit-zoom-info").textContent = !k ? "" : z ? `zoom padrão do kit: ${z}` : "este kit não tem zoom padrão (defina na Biblioteca de estilos)";
}
const salvarMarca = () => tentar(() => salvarProjeto({ marca: { arquivo: $("#marca-arquivo").value || null, pos: $("#marca-pos").value,
  tamanho: +$("#marca-tamanho").value, opacidade: +$("#marca-opacidade").value } }));
["#marca-arquivo", "#marca-pos", "#marca-tamanho", "#marca-opacidade"].forEach((s) => ($(s).onchange = salvarMarca));
$("#marca-upload").onchange = (e) => tentar(async () => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("arquivo", f, f.name);
  const r = await api("POST", "/api/kits/logos", fd); KITS = r; e.target.value = "";
  renderKit(); $("#marca-arquivo").value = r.logo; await salvarMarca();
});
$("#kit-salvar").onclick = () => tentar(async () => {
  const nome = prompt("Nome do kit (ex.: Meu canal GTA):"); if (!nome) return;
  const k = await api("POST", "/api/kits", { nome, projeto: P.nome });
  await carregarKits(); renderKit(); $("#kit-sel").value = k.id; aviso(`Kit “${k.nome}” salvo. Use-o ao criar projetos novos.`);
});
$("#kit-aplicar").onclick = () => tentar(async () => {
  const id = $("#kit-sel").value; if (!id) throw new Error("salve um kit primeiro");
  const antes = fotografia();
  const r = await api("POST", `${base()}/kit`, { kit: id }); P = r;
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); aviso(r.aviso ? `Kit aplicado sem o logo: ${r.aviso}` : "Kit aplicado (Ctrl+Z desfaz).", !!r.aviso);
});
$("#kit-excluir").onclick = () => tentar(async () => {
  const id = $("#kit-sel").value; if (!id || !confirm("Excluir este kit? (os projetos que já usam o estilo não mudam)")) return;
  KITS = await api("DELETE", `/api/kits/${encodeURIComponent(id)}`); renderKit();
});
$("#kit-sel").onchange = () => renderKit();
$("#kit-biblioteca").onclick = () => tentar(() => abrirBiblioteca($("#kit-sel").value || null));
$("#kit-zoom").onclick = () => tentar(async () => {
  const id = $("#kit-sel").value; if (!id) throw new Error("salve um kit primeiro");
  if (!P.segmentos.length) throw new Error("a timeline está vazia");
  const antes = fotografia();
  const r = await api("POST", `${base()}/kit/zoom`, { kit: id }); P = r;
  if (r.aplicados.length) { historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico(); }
  renderTudo();
  aviso(r.aplicados.length ? `Zoom do kit em ${r.aplicados.length} trecho(s) que estavam sem zoom: ${r.aplicados.map((n) => "#" + n).join(", ")}. Confira com “▶ Prévia exata”.`
    : "Todos os trechos já têm zoom: nada mudou.", false, r.aplicados.length ? { rotulo: "Desfazer", fn: desfazer } : null);
});
const nomeZoom = (fx) => (fx ? ZOOM?.presets?.[fx.preset]?.nome || "personalizado" : null);
