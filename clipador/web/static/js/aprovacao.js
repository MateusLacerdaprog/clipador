// Clipador - janela Aprovacao: rascunhos de todos os projetos esperando o usuario e os FINAIS aprovados.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

let apItens = [], apSel = null, apFiltro = "pendentes";
const AP_ROTULO = { aguardando: "esperando você", aprovado_sem_final: "aprovado, falta o FINAL",
  desatualizado: "mudou depois do vídeo: gere de novo", aprovado: "aprovado" };
const apArq = (nome, rel) => `/api/projetos/${encodeURIComponent(nome)}/arquivo?caminho=${encodeURIComponent(rel)}&t=${Date.now()}`;

async function abrirAprovacao() {
  apItens = (await api("GET", "/api/aprovacao")).itens;
  renderAprovacao();
  if (!$("#dlg-aprovacao").open) $("#dlg-aprovacao").showModal();
}
function renderAprovacao() {
  $$("[data-filtro-ap]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.filtroAp === apFiltro));
  const vis = apItens.filter((i) => (i.estado === "aprovado") === (apFiltro === "aprovados"));
  $("#ap-lista").innerHTML = vis.map((i) => `<div role="listitem" class="linha"><button type="button" class="saida${i.nome === apSel ? " ativa" : ""}" data-ap="${esc(i.nome)}" aria-pressed="${i.nome === apSel}">${esc(i.nome)}</button>`
    + `<span class="dica">${esc(AP_ROTULO[i.estado])} · ${i.editor === "editonny" ? "editonny" : "Clipador"}${i.nota ? " · ajuste pedido" : ""}</span></div>`).join("")
    || `<p class="dica">${apFiltro === "aprovados" ? "Nenhum vídeo aprovado ainda." : "Nada esperando você."}</p>`;
  const i = apItens.find((x) => x.nome === apSel);
  $("#ap-detalhe").hidden = !i;
  if (!i) return;
  $("#ap-nome").textContent = `${i.nome} — ${AP_ROTULO[i.estado]}`;
  const video = i.estado === "aprovado" ? i.final : i.rascunho || i.final;
  if (video && !$("#ap-player").src.includes(encodeURIComponent(video))) $("#ap-player").src = apArq(i.nome, video);
  $("#ap-nota").value = i.nota;
  $("#ap-aprovar").disabled = i.estado !== "aguardando" && i.estado !== "aprovado_sem_final";
}
$("#abrir-aprovacao").onclick = () => tentar(abrirAprovacao);
$$("[data-filtro-ap]").forEach((b) => (b.onclick = () => { apFiltro = b.dataset.filtroAp; apSel = null; renderAprovacao(); }));
$("#ap-lista").onclick = (e) => { const n = e.target.dataset.ap; if (n) { apSel = n; renderAprovacao(); } };
$("#ap-aprovar").onclick = () => tentar(async () => {
  const nome = apSel;
  const r = await acompanhar(await api("POST", `/api/aprovacao/${encodeURIComponent(nome)}/aprovar`), "#ap-tarefa");
  aviso(`${nome} aprovado: ${r.arquivo} gerado${r.publicacao ? " com o PUBLICACAO.md" : ""}.`);
  await abrirAprovacao();
});
$("#ap-ajuste").onclick = () => tentar(async () => {
  await api("POST", `/api/aprovacao/${encodeURIComponent(apSel)}/ajuste`, { nota: $("#ap-nota").value });
  aviso("Recado salvo. Peça ao Claude a nova versão.");
  await abrirAprovacao();
});
$("#ap-abrir").onclick = () => tentar(async () => { const n = apSel; $("#dlg-aprovacao").close(); await abrirProjeto(n); });
