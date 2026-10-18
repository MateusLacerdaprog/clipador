// Clipador - aba 7 Revisar: quadros, RASCUNHO, aprovar, FINAL.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// -------------------------------------------------------------------- 6 REVISAR
function renderRevisar() {
  if (!$("#tempos").value && P.duracao) {
    const d = P.duracao; $("#tempos").value = [0.5, d * 0.25, d * 0.5, d * 0.75, d - 0.5].map((t) => t.toFixed(1)).join(", ");
  }
  $("#aprovar").disabled = !P.rascunho_atual || P.aprovado_atual;
  $("#gerar-final").disabled = !P.aprovado_atual;
  $("#status-aprov").innerHTML = P.aprovado_atual ? `<span class="selo ok">rascunho atual APROVADO</span>`
    : P.rascunho_atual ? `<span class="selo pend">rascunho atual aguardando sua aprovação</span>`
    : `<span class="selo">gere um rascunho da versão atual</span>`;
  $("#lista-saidas").innerHTML = P.saidas.map((s) => `<div class="saida-par"><button type="button" class="saida ${s.startsWith("FINAL") ? "final" : ""}${s === saidaSel ? " ativa" : ""}" data-s="${esc(s)}" aria-pressed="${s === saidaSel}">${esc(s)}</button>`
    + `<button type="button" class="mini" data-excluir-saida="${esc(s)}" title="apaga este arquivo do projeto" aria-label="Excluir ${esc(s)}">✕</button></div>`).join("")
    || `<p class="dica">Nenhum vídeo gerado ainda.</p>`;
  const comCaps = !!P.formato_cfg?.capitulos;
  $("#bloco-capitulos").hidden = !comCaps;
  if (comCaps) api("GET", `${base()}/capitulos`).then((c) => {
    $("#txt-capitulos").value = c.texto || "(escreva o rótulo dos trechos que abrem cada capítulo na aba Cortes)";
    $("#avisos-capitulos").textContent = c.avisos.join(" ");
  }).catch(() => {});
}
$("#copiar-capitulos").onclick = () => tentar(async () => { await navigator.clipboard.writeText($("#txt-capitulos").value); aviso("Capítulos copiados. Cole na descrição do YouTube."); });
let saidaSel = null;
$("#lista-saidas").onclick = (e) => {
  const ex = e.target.dataset.excluirSaida;
  if (ex) return tentar(async () => {          // arquivo de vídeo apagado de verdade: aqui a confirmação faz sentido
    if (!confirm(`Apagar ${ex}? O arquivo sai da pasta do projeto (o projeto continua; dá para gerar de novo).`)) return;
    P = await api("DELETE", `${base()}/saidas/${encodeURIComponent(ex)}`);
    if (saidaSel === ex) { saidaSel = null; $("#player-saida").removeAttribute("src"); habilitarDerivados(null); }
    renderTudo(); aviso(`${ex} apagado.`);
  });
  const s = e.target.dataset.s; if (!s) return;
  saidaSel = s; habilitarDerivados(s);
  document.querySelectorAll("#lista-saidas .saida").forEach((el) => el.classList.toggle("ativa", el.dataset.s === s));
  $("#player-saida").src = arq(s); $("#player-saida").play().catch(() => {});
};
$("#exportar-1x1").onclick = () => tentar(async () => {
  if (!saidaSel) throw new Error("clique primeiro num RASCUNHO ou FINAL da lista");
  const r = await acompanhar(await api("POST", `${base()}/exportar_1x1`, { arquivo: saidaSel }), "#tarefa-render");
  P = await api("GET", base()); renderTudo();
  aviso(`Versão 1:1 gerada: ${r.saida} (confira o enquadramento antes de postar).`);
});
function habilitarDerivados(s) {        // versoes feitas a partir do video selecionado (1:1 e sem audio)
  $("#exportar-1x1").disabled = !s || s.endsWith("_1x1.mp4");
  $("#exportar-sem-audio").disabled = !s || s.includes("_sem_audio");
}
$("#exportar-sem-audio").onclick = () => tentar(async () => {
  if (!saidaSel) throw new Error("clique primeiro num RASCUNHO ou FINAL da lista");
  const r = await api("POST", `${base()}/exportar_sem_audio`, { arquivo: saidaSel });
  P = r.estado; renderTudo();
  aviso(`Versão sem áudio gerada: ${r.saida}. Ponha a música dentro do TikTok/Reels.`);
});
$("#revisar-mudo").onchange = (e) => {   // assistir como a maioria assiste Shorts: sem som
  $("#player-saida").muted = e.target.checked;
  $("#dica-mudo").hidden = !e.target.checked;
};
$("#gerar-quadros").onclick = () => tentar(async () => {
  const tempos = $("#tempos").value.split(/[,;\s]+/).map(Number).filter((x) => !isNaN(x));
  const lista = await acompanhar(await api("POST", `${base()}/quadros`, { tempos }), "#tarefa-quadros");
  $("#grade-quadros").innerHTML = lista.map((q) => `<figure><a href="${arq(q)}" target="_blank" rel="noopener"><img alt="Quadro em ${esc(q.match(/([\d.]+)s\.png$/)?.[1] || "")} s" src="${arq(q)}"></a>
    <figcaption>${esc(q.match(/([\d.]+)s\.png$/)?.[1] || "")} s</figcaption></figure>`).join("");
});
$("#excluir-quadros").onclick = () => tentar(async () => {
  const r = await api("DELETE", `${base()}/quadros`);
  $("#grade-quadros").innerHTML = ""; aviso(r.apagados ? `${r.apagados} quadro(s) apagado(s).` : "Não havia quadros.");
});
$("#excluir-projeto").onclick = () => tentar(async () => {
  const nome = P.nome;
  if (!confirm(`Excluir o projeto “${nome}”? Ele vai para a lixeira (projetos/_lixeira) e dá para desfazer em seguida.`)) return;
  const r = await api("DELETE", base());
  P = null; localStorage.removeItem("clipador.projeto");
  $("#editor").hidden = true; $("#vazio").hidden = false; await carregarLista();
  aviso(`Projeto “${nome}” na lixeira.`, false, { rotulo: "Desfazer", fn: () => tentar(async () => {
    const p = await api("POST", `/api/lixeira/${encodeURIComponent(r.lixeira)}/restaurar`); await abrirProjeto(p.nome); aviso("Projeto restaurado.");
  }) });
});
$("#gerar-rascunho").onclick = () => tentar(async () => {
  const r = await acompanhar(await api("POST", `${base()}/render/rascunho`), "#tarefa-render");
  await recarregar(); $("#player-saida").src = arq(r.arquivo);
  aviso("RASCUNHO pronto. Assista inteiro antes de aprovar.");
});
$("#aprovar").onclick = () => tentar(async () => {
  if (!confirm("Você assistiu o rascunho inteiro e aprova esta versão?")) return;
  P = await api("POST", `${base()}/aprovar`); renderTudo();
});
$("#gerar-final").onclick = () => tentar(async () => {
  const r = await acompanhar(await api("POST", `${base()}/render/final`), "#tarefa-render");
  await recarregar(); $("#player-saida").src = arq(r.arquivo); aviso("FINAL gerado: " + r.arquivo);
});
