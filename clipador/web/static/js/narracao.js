// Clipador - aba 5 Narracao: gravacao sobre a previa.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------------ 5 NARRACAO
let gravador = null, pedacos = [], blobGravado = null, streamMic = null, analisador = null, t0 = 0, relogio = null;

function renderNarracao() {
  $("#roteiro").value = P.roteiro || "";
  // o player so recarrega quando a previa muda de verdade (antes recarregava a cada redesenho e voltava ao zero)
  const v = $("#player-proxy"), chave = P.tem_proxy ? `${P.nome}:${P.proxy_versao}` : "";
  if (v.dataset.versao !== chave) {
    v.dataset.versao = chave;
    if (P.tem_proxy) v.src = urlProxy(); else v.removeAttribute("src");
  }
  $("#estado-proxy").innerHTML = !P.tem_proxy ? `<span class="selo">ainda não gerada</span>`
    : P.proxy_atual ? `<span class="selo ok">✓ em dia com a montagem (${P.duracao.toFixed(1)} s)</span>`
    : `<span class="selo pend">⚠ a montagem mudou depois desta prévia: gere de novo</span>`;
  $("#gerar-proxy").textContent = !P.tem_proxy ? "Gerar prévia da montagem" : P.proxy_atual ? "Gerar a prévia de novo" : "Atualizar a prévia";
  $("#gerar-proxy").classList.toggle("primario", !P.proxy_atual);
  $("#com-narracao").disabled = !P.narracao;
  if (!P.narracao) $("#com-narracao").checked = false;
  $("#narr-atual").innerHTML = P.narracao
    ? `${esc(P.narracao)} · ${P.narracao_dur.toFixed(1)} s (vídeo: ${P.duracao.toFixed(1)} s)` +
      (P.narracao_dur > P.duracao + 0.3 ? ` — <b style="color:var(--rosa)">a narração é mais longa que o vídeo e será cortada</b>` : "") +
      ` <audio controls src="${arq(P.narracao)}" style="vertical-align:middle;height:32px"></audio> <button id="remover-narr">Remover</button>`
    : "Nenhuma. (Sem narração o vídeo sai com o som do jogo — bom para comparações e cortes rápidos.)";
}
const urlProxy = () => `${base()}/arquivo?caminho=proxy.mp4&v=${P.proxy_versao}`;
// previa com a narracao ja gravada: um <audio> segue o video (play, pausa, pulo, velocidade e deslocamento da trilha)
const audioSync = new Audio();
let srcSync = "";
function seguirVideo(v, a, ligado) {      // um <audio> com a narracao acompanha o video (play, pausa, pulo, velocidade)
  if (!ligado || !P || !P.narracao || (gravador && gravador.state === "recording")) { a.pause(); return; }
  const src = `${base()}/arquivo?caminho=${encodeURIComponent(P.narracao)}&v=${P.narracao_dur}`;
  if (a.dataset.src !== src) { a.dataset.src = src; a.src = src; }
  const alvo = v.currentTime - (+(P.audio?.narracao?.deslocamento) || 0);
  if (alvo < 0 || alvo > P.narracao_dur) { a.pause(); return; }
  if (Math.abs(a.currentTime - alvo) > 0.15) a.currentTime = alvo;
  a.playbackRate = v.playbackRate;
  if (v.paused) a.pause(); else a.play().catch(() => {});
}
const sincronizarNarracao = () => seguirVideo($("#player-proxy"), audioSync, $("#com-narracao").checked);
