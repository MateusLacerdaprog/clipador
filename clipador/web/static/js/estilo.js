// Clipador - aba 3 Estilo.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// -------------------------------------------------------------------- 3 ESTILO
function renderEstilo() {
  renderKit();
  const longo = P.tipo === "longo";
  $("#card-layout-curto").hidden = longo; $("#card-layout-longo").hidden = !longo;
  if (CATALOGO) $("#sel-formato").innerHTML = CATALOGO[P.tipo || "curto"].map((f) =>
    `<option value="${f.id}" ${(P.formato || "livre") === f.id ? "selected" : ""}>${f.icone} ${esc(f.nome)}</option>`).join("");
  $("#cfg-ranking").checked = !!P.formato_cfg?.ranking; $("#cfg-ranking").closest(".linha").hidden = longo;
  $("#cfg-capitulos").checked = !!P.formato_cfg?.capitulos;
  $("#leg-y").max = longo ? 1060 : 1520; $("#leg-y").min = longo ? 100 : 300;
  $$('#op-layout input').forEach((r) => (r.checked = r.value === P.layout));
  $("#leg-estilo").value = P.legenda.estilo;
  $("#leg-y").value = P.legenda.pos_y ?? "";
  $("#leg-maius").checked = !!P.legenda.maiusculas;
}
$("#aplicar-formato").onclick = () => tentar(async () => {
  const f = $("#sel-formato").value;
  if (!confirm("Aplicar o preset deste formato? Layout, legenda e áudio mudam; trechos, textos e narração ficam.")) return;
  const antes = fotografia();
  P = await api("POST", `${base()}/formato`, { formato: f === "livre" ? null : f });
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); renderGuia(); carregarLista(); aviso("Preset aplicado. Pode desfazer com Ctrl+Z.");
});
$("#cfg-ranking").onchange = () => salvarAudioCfg();
$("#cfg-capitulos").onchange = () => salvarAudioCfg();
const salvarAudioCfg = () => tentar(() => salvarProjeto({ formato_cfg: { ranking: $("#cfg-ranking").checked, capitulos: $("#cfg-capitulos").checked } }));
const salvarEstilo = () => tentar(async () => {
  const layout = P.tipo === "longo" ? "horizontal" : ($('#op-layout input:checked')?.value || P.layout);
  await salvarProjeto({
    layout,
    legenda: { estilo: $("#leg-estilo").value, pos_y: $("#leg-y").value ? +$("#leg-y").value : null, maiusculas: $("#leg-maius").checked },
  });
});
["#leg-estilo", "#leg-y", "#leg-maius"].forEach((s) => ($(s).onchange = salvarEstilo));
document.addEventListener("click", (e) => { const b = e.target.closest("[data-ir-aba]"); if (b) irParaAba(b.dataset.irAba); });
$("#op-layout").onchange = salvarEstilo;
