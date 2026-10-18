// Clipador - atalhos de teclado e inicializacao (carrega por ultimo).
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------------ atalhos
$("#desfazer").onclick = desfazer;
$("#refazer").onclick = refazer;
$("#ajuda-atalhos").onclick = () => $("#dlg-atalhos").showModal();
document.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("#cc-texto").focus(); return; }   // centro de comando
  const campo = e.target.closest && e.target.closest("input, textarea, select, [contenteditable]");
  if (e.key === "Escape" && campo) { e.target.blur(); return; }
  if (campo || !P) return;                       // dentro de um campo vale o desfazer do proprio campo
  const k = e.key.toLowerCase();
  if ((e.ctrlKey || e.metaKey) && k === "z" && !e.shiftKey) { e.preventDefault(); desfazer(); }
  else if ((e.ctrlKey || e.metaKey) && (k === "y" || (k === "z" && e.shiftKey))) { e.preventDefault(); refazer(); }
  else if (e.altKey && /^[1-9]$/.test(e.key)) { e.preventDefault(); $$("#abas button")[+e.key - 1]?.click(); }
  else if (!$("[data-painel=cortes]").hidden && !e.ctrlKey && !e.altKey && !e.metaKey && e.target.closest("#tlv")) {   // so com o foco na timeline
    const k2 = e.key;
    if (k2 === " ") { e.preventDefault(); tocandoTL ? pararTimeline() : tocarTimeline(); }
    else if (k2.toLowerCase() === "s") { e.preventDefault(); dividirNoCursor(); }
    else if (k2.toLowerCase() === "d") { e.preventDefault(); duplicarSel(); }
    else if (k2 === "Delete" || k2 === "Backspace") { e.preventDefault(); removerSel(); }
    else if (k2 === "ArrowLeft" || k2 === "ArrowRight") { e.preventDefault(); pararTimeline();
      cursorV = Math.max(0, Math.min(P.duracao, cursorV + (k2 === "ArrowLeft" ? -1 : 1) * (e.shiftKey ? 1 : 0.1))); atualizarTempoTL(); }
  }
  else if (e.key === " " && !$("[data-painel=audio]").hidden && e.target === document.body) {   // Espaço num botao continua ativando o botao
    e.preventDefault(); const a = $("#audio-previa"); if (a.src) (a.paused ? a.play().catch(() => {}) : a.pause());
  }
});

// ------------------------------------------------------------------------ início
(async () => {
  await tentar(async () => { CATALOGO = await api("GET", "/api/formatos"); });
  await tentar(carregarLista);
  const ultimo = localStorage.getItem("clipador.projeto");
  if (ultimo) abrirProjeto(ultimo).catch(() => localStorage.removeItem("clipador.projeto"));  // projeto apagado: ignora
})();
