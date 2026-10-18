// Clipador - biblioteca de estilos: kits do canal e presets de zoom.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ---- biblioteca de estilos: kits editados sem projeto + presets de zoom do usuario
let BK = null, bkSujo = false;
const VALORES_ZOOM = ["intensidade", "inicio", "duracao", "curva", "volta", "segura"];
async function abrirBiblioteca(id) {
  await carregarKits();
  ZOOM = await api("GET", "/api/zoom/presets");
  if (!PLATS) PLATS = await api("GET", "/api/legendas/plataformas");
  renderBiblioteca(id || BK?.id);
  $("#dlg-kits").showModal();
}
function renderBiblioteca(id) {
  BK = KITS.kits.find((k) => k.id === id) || KITS.kits[0] || null;
  $("#bk-sel").innerHTML = KITS.kits.length ? KITS.kits.map((k) => `<option value="${esc(k.id)}">${esc(k.nome)}</option>`).join("") : `<option value="">(nenhum kit: crie um)</option>`;
  if (BK) $("#bk-sel").value = BK.id;
  $("#bk-duplicar").disabled = $("#bk-excluir").disabled = !BK;
  $("#bk-form").hidden = !BK;
  if (BK) preencherKit(BK);
  renderPresetsZoom();
}
function opcoesZoom(fx) {
  const sel = fx ? (ZOOM.presets[fx.preset] ? fx.preset : "personalizado") : "nenhum";
  return [["nenhum", "sem zoom padrão"], ...Object.entries(ZOOM.presets).map(([k, p]) => [k, p.nome + (p.usuario ? " (seu)" : "")]),
    ...(sel === "personalizado" ? [["personalizado", "personalizado (valores guardados)"]] : [])]
    .map(([k, n]) => `<option value="${esc(k)}" ${k === sel ? "selected" : ""}>${esc(n)}</option>`).join("");
}
function preencherKit(k) {
  const L = k.legenda || {}, M = k.marca || {};
  $("#bk-nome").value = k.nome; $("#bk-layout").value = k.layout || "tela_cheia"; $("#bk-gancho").value = k.gancho_ate ?? 3;
  $("#bk-leg-estilo").value = L.estilo || "karaoke"; $("#bk-leg-maius").checked = !!L.maiusculas; $("#bk-leg-y").value = L.pos_y ?? "";
  $("#bk-leg-fonte").innerHTML = PLATS.fontes.map((f) => `<option ${f === (L.fonte || "Arial Black") ? "selected" : ""}>${esc(f)}</option>`).join("");
  $("#bk-leg-tamanho").value = L.tamanho ?? ""; $("#bk-leg-contorno").value = L.contorno ?? ""; $("#bk-leg-sombra").value = L.sombra ?? "";
  $("#bk-leg-cor").value = L.cor || "#ffffff"; $("#bk-leg-destaque").value = L.destaque || "#ffde00"; $("#bk-leg-animacao").value = L.animacao || "nenhuma";
  const sumiu = M.arquivo && !KITS.logos.includes(M.arquivo);
  $("#bk-marca-arquivo").innerHTML = `<option value="">sem logo</option>` + KITS.logos.map((l) => `<option ${l === M.arquivo ? "selected" : ""}>${esc(l)}</option>`).join("");
  $("#bk-marca-pos").value = M.pos || "sup_dir"; $("#bk-marca-tamanho").value = M.tamanho ?? 0.14; $("#bk-marca-opacidade").value = M.opacidade ?? 0.85;
  $("#bk-zoom").innerHTML = opcoesZoom(k.zoom_padrao); dicaZoomKit();
  bkSujo = false;
  $("#bk-status").textContent = sumiu ? `O logo “${M.arquivo}” não está mais em kits/logos: escolha outro e salve.` : "";
}
function dicaZoomKit() {
  const v = $("#bk-zoom").value, p = ZOOM.presets[v];
  $("#bk-zoom-dica").textContent = p ? `${(+p.intensidade).toFixed(2)}× — ${p.dica || ""}` : v === "personalizado" ? "valores guardados no kit" : "";
}
$("#bk-zoom").onchange = dicaZoomKit;
$("#bk-form").addEventListener("input", () => { bkSujo = true; $("#bk-status").textContent = "alterações não salvas"; });
$("#bk-sel").onchange = (e) => {
  if (bkSujo && !confirm("Descartar as mudanças não salvas deste kit?")) { e.target.value = BK.id; return; }
  renderBiblioteca(e.target.value);
};
$("#bk-form").onsubmit = (e) => { e.preventDefault(); tentar(async () => {
  const n = (id) => ($(id).value === "" ? null : +$(id).value), z = $("#bk-zoom").value, pr = ZOOM.presets[z], ant = BK.zoom_padrao || {};
  const zoom_padrao = z === "nenhum" ? null : z === "personalizado" ? BK.zoom_padrao
    : { preset: z, ...Object.fromEntries(VALORES_ZOOM.map((c) => [c, pr[c]])), foco_x: ant.foco_x ?? 0.5, foco_y: ant.foco_y ?? 0.5 };
  const k = await api("PUT", `/api/kits/${encodeURIComponent(BK.id)}`, {
    nome: $("#bk-nome").value, layout: $("#bk-layout").value, gancho_ate: +$("#bk-gancho").value || 0, zoom_padrao,
    legenda: { estilo: $("#bk-leg-estilo").value, maiusculas: $("#bk-leg-maius").checked, pos_y: n("#bk-leg-y"), fonte: $("#bk-leg-fonte").value,
      tamanho: n("#bk-leg-tamanho"), contorno: n("#bk-leg-contorno"), sombra: n("#bk-leg-sombra"), cor: $("#bk-leg-cor").value,
      destaque: $("#bk-leg-destaque").value, animacao: $("#bk-leg-animacao").value },
    marca: { arquivo: $("#bk-marca-arquivo").value || null, pos: $("#bk-marca-pos").value, tamanho: +$("#bk-marca-tamanho").value,
      opacidade: +$("#bk-marca-opacidade").value } });
  await carregarKits(); renderBiblioteca(k.id); renderKit();
  $("#bk-status").textContent = "✓ kit salvo";
  aviso(`Kit “${k.nome}” salvo. Para usar num projeto: aba 3 · Estilo → Aplicar kit.`);
}); };
$("#bk-novo").onclick = () => tentar(async () => {
  const nome = prompt("Nome do novo kit (ex.: Canal GTA — notícias):"); if (!nome) return;
  const k = await api("POST", "/api/kits", { nome });
  await carregarKits(); renderBiblioteca(k.id); renderKit(); aviso(`Kit “${k.nome}” criado com o estilo padrão. Ajuste e clique em Salvar kit.`);
});
$("#bk-duplicar").onclick = () => tentar(async () => {
  const nome = prompt("Nome da cópia:", `${BK.nome} (cópia)`); if (!nome) return;
  const k = await api("POST", `/api/kits/${encodeURIComponent(BK.id)}/duplicar`, { nome });
  await carregarKits(); renderBiblioteca(k.id); renderKit(); aviso(`Kit duplicado: “${k.nome}”.`);
});
$("#bk-excluir").onclick = () => tentar(async () => {
  if (!BK || !confirm(`Excluir o kit “${BK.nome}”? (os projetos que já usam o estilo não mudam)`)) return;
  KITS = await api("DELETE", `/api/kits/${encodeURIComponent(BK.id)}`); renderBiblioteca(); renderKit();
});
function renderPresetsZoom() {
  const curva = { suave: "suave", rapida: "rápida", linear: "constante" };
  $("#bk-zoom-lista").innerHTML = Object.entries(ZOOM.presets).map(([id, p]) => `<li><b>${esc(p.nome)}</b>
    <span class="dica">${(+p.intensidade).toFixed(2)}× · ${p.duracao ? p.duracao + " s" : "o trecho todo"} · ${curva[p.curva] || p.curva}${p.volta ? ` · volta (segura ${p.segura} s)` : ""}${p.dica ? " — " + esc(p.dica) : ""}</span>
    ${p.usuario ? `<button type="button" class="mini" data-bz-excluir="${esc(id)}" aria-label="Excluir o preset de zoom ${esc(p.nome)}">Excluir</button>` : `<span class="chip">embutido</span>`}</li>`).join("");
}
async function zoomPresetsMudaram(r) {
  ZOOM = { presets: r.presets, curvas: r.curvas, embutidos: r.embutidos };
  renderPresetsZoom();
  if (BK) { const v = $("#bk-zoom").value; $("#bk-zoom").innerHTML = opcoesZoom(BK.zoom_padrao); if (ZOOM.presets[v] || v === "nenhum") $("#bk-zoom").value = v; dicaZoomKit(); }
  if (P) renderTudo();
}
$("#bz-salvar").onclick = () => tentar(async () => {
  const r = await api("POST", "/api/zoom/presets", { nome: $("#bz-nome").value, intensidade: +$("#bz-intensidade").value, inicio: +$("#bz-inicio").value,
    duracao: +$("#bz-duracao").value, curva: $("#bz-curva").value, volta: $("#bz-volta").checked, segura: +$("#bz-segura").value, dica: $("#bz-dica").value });
  await zoomPresetsMudaram(r); $("#bz-nome").value = ""; $("#bz-dica").value = "";
  aviso(`Preset de zoom “${r.presets[r.id].nome}” salvo. Ele já aparece no menu Zoom dos trechos.`);
});
$("#bk-zoom-lista").onclick = (e) => tentar(async () => {
  const id = e.target.dataset.bzExcluir; if (!id) return;
  const nome = ZOOM.presets[id]?.nome || id;
  if (!confirm(`Excluir o preset de zoom “${nome}”? Os trechos que já usam ficam como estão (viram “personalizado”).`)) return;
  await zoomPresetsMudaram(await api("DELETE", `/api/zoom/presets/${encodeURIComponent(id)}`));
  aviso(`Preset “${nome}” excluído.`);
});
$("#abrir-kits").onclick = () => tentar(() => abrirBiblioteca(null));
