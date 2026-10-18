// Clipador - aba 6 Textos: previa editavel, legendas, presets por plataforma e tempo por palavra.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ---- aba 6 · Textos: prévia ao vivo (aproximação do .ass) com TODO texto clicável para editar no próprio vídeo
let PLATS_LEG = null;
const audioLeg = new Audio();
const descLeg = () => +(P?.desloc_legenda) || 0;               // tempo no vídeo = tempo do cartão + isto
async function prepararPreviaLegenda() {
  if (!PLATS_LEG) PLATS_LEG = await api("GET", "/api/legendas/plataformas");
  const v = $("#leg-video"), chave = P.tem_proxy ? `${P.nome}:${P.proxy_versao}` : "";
  if (v.dataset.versao !== chave) { v.dataset.versao = chave; if (P.tem_proxy) v.src = urlProxy(); else v.removeAttribute("src"); }
  $("#leg-sem-previa").hidden = !!P.tem_proxy && P.proxy_atual;
  $("#leg-sem-previa span").textContent = !P.tem_proxy ? "Para editar em cima do vídeo, gere a prévia da montagem (leva alguns segundos)."
    : "A montagem mudou depois desta prévia: gere de novo para ver o vídeo certo.";
  $("#tx-gerar-previa").textContent = P.tem_proxy ? "Atualizar a prévia" : "Gerar prévia";
  desenharLegenda();
}
$("#tx-gerar-previa").onclick = () => tentar(async () => {
  await acompanhar(await api("POST", `${base()}/proxy`), "#tarefa-tx-previa");
  await recarregar(); await prepararPreviaLegenda(); aviso("Prévia pronta: pause e clique num texto para editar.");
});
function geometria() {                       // área real do vídeo dentro do palco (contain), em px do palco
  const v = $("#leg-video"), longo = P.tipo === "longo", W = longo ? 1920 : 1080, H = longo ? 1080 : 1920;
  const pr = v.parentElement.getBoundingClientRect();
  if (!v.videoHeight) { const w = Math.min(pr.width, 300); return { W, H, s: w / W, ox: 0, oy: 0, w, h: w * H / W, longo }; }
  const r = v.getBoundingClientRect(), s = Math.min(r.width / W, r.height / H);
  const w = W * s, h = H * s;
  return { W, H, s, w, h, longo, ox: r.left - pr.left + (r.width - w) / 2, oy: r.top - pr.top + (r.height - h) / 2 };
}
function cartaoNoInstante(tv) {             // tv = tempo do vídeo
  const t = tv - descLeg();
  return cartoes.findIndex((c, k) => {
    const ps = c.palavras, prox = cartoes[k + 1];
    const fim = Math.min(ps[ps.length - 1].end + 0.12, prox ? prox.palavras[0].start - 0.01 : Infinity);
    return t >= ps[0].start && t < fim;
  });
}
function trechoNoInstante(t) {
  let acc = 0;
  for (const s of P.segmentos) { const d = s.fim - s.ini; if (t < acc + d) return s; acc += d; }
  return P.segmentos[P.segmentos.length - 1];
}
function desenharLegenda() {
  const v = $("#leg-video"), ov = $("#leg-overlay"), alvos = ["#leg-overlay", "#tx-ov-gancho", "#tx-ov-rot-a", "#tx-ov-rot-b"];
  if (!PLATS_LEG || !P || !v.videoHeight) { alvos.forEach((s) => ($(s).hidden = true)); return; }
  const g = geometria(), t = v.currentTime, k = g.longo ? 0.7 : 1;
  $("#tx-tempo").textContent = `${mmss(t)} / ${mmss(P.duracao)}`;
  const lay = g.longo ? "horizontal" : P.layout, pos = PLATS_LEG.posicoes[lay] || PLATS_LEG.posicoes.empilhado;
  // título do início (estilo Gancho do .ass: caixa vermelha, branco, MAIÚSCULAS, topo)
  const G = P.gancho || {}, ateG = +G.ate || 0, bg = $("#tx-ov-gancho");
  bg.hidden = !(G.texto && (ateG === 0 || t < ateG));
  if (!bg.hidden) {
    bg.textContent = G.texto.toUpperCase();
    bg.style.cssText = `left:${g.ox + g.W / 2 * g.s}px;top:${g.oy + pos.gancho * g.s}px;max-width:${(g.W - 120) * g.s}px;` +
      `font-size:${72 * k * g.s}px;padding:${8 * g.s}px ${16 * g.s}px;`;
  }
  // rótulos da comparação (colados na linha do meio: A acima, B abaixo)
  const comp = P.layout === "comparacao" && !g.longo, seg = comp && P.segmentos.length ? trechoNoInstante(t) : null;
  for (const [sel, lado, y, sobe] of [["#tx-ov-rot-a", "a", 935, true], ["#tx-ov-rot-b", "b", 985, false]]) {
    const el = $(sel), txt = seg ? (seg[`rotulo_${lado}`] || P.comparacao?.[`rotulo_${lado}`] || "") : "";
    el.hidden = !txt;
    if (txt) { el.textContent = txt.toUpperCase(); el.style.cssText = `left:${g.ox + 40 * g.s}px;top:${g.oy + y * g.s}px;font-size:${64 * g.s}px;${sobe ? "transform:translateY(-100%);" : ""}`; }
  }
  // legenda do instante
  const i = cartaoNoInstante(t);
  ov.hidden = i < 0; if (i < 0) return;
  ov.dataset.i = i;
  const L = P.legenda, E = PLATS_LEG.estilos[L.estilo] || PLATS_LEG.estilos.karaoke;
  const y = L.pos_y || pos.legenda, x = g.longo ? g.W / 2 : PLATS_LEG.pos_x;
  const ps = cartoes[i].palavras, j = ps.findLastIndex((p) => p.start <= t - descLeg());
  const cor = L.cor || "#ffffff", dest = L.destaque || "#ffde00";
  const cont = (L.contorno ?? E.contorno) * g.s, sombra = (L.sombra ?? E.sombra) * g.s;
  ov.className = "tx-alvo tx-legenda" + (E.caixa ? " caixa" : "") + (P.legendas_invisiveis ? " invisivel" : "");
  ov.style.cssText = `left:${g.ox + x * g.s}px;top:${g.oy + y * g.s}px;max-width:${g.w * 0.86}px;font-family:"${L.fonte || "Arial Black"}","Arial Black",sans-serif;` +
    `font-size:${(L.tamanho || E.tamanho) * k * g.s}px;` +
    (E.caixa ? `background:${cor};padding:${4 * g.s}px ${14 * g.s}px;` : `-webkit-text-stroke:${cont * 2}px #000;text-shadow:${sombra}px ${sombra}px 0 #0009;`);
  ov.innerHTML = ps.map((p, n) => {
    const txt = esc(L.maiusculas ? p.w.toUpperCase() : p.w);
    if (E.caixa) return p.e ? `<u>${txt}</u>` : txt;
    return `<span style="color:${n === j || p.e ? dest : cor}">${txt}</span>`;
  }).join(" ");
}
(() => {
  const v = $("#leg-video");
  const passo = () => { desenharLegenda(); seguirVideo(v, audioLeg, P && !P.legendas_invisiveis && P.legenda_origem === "narracao"); if (!v.paused) requestAnimationFrame(passo); };
  ["play", "seeked", "loadedmetadata", "pause", "ratechange"].forEach((ev) => v.addEventListener(ev, passo));
  v.addEventListener("play", fecharEditor);
  window.addEventListener("resize", desenharLegenda);
})();

// editor que abre em cima do texto clicado (Enter salva, Esc cancela)
let EDIT = null;
const TITULOS_ED = { legenda: "Legenda", gancho: "Título do início", rot_a: "Rótulo do vídeo de cima", rot_b: "Rótulo do vídeo de baixo", nova: "Nova legenda" };
const ALVO_ED = { legenda: "#leg-overlay", gancho: "#tx-ov-gancho", rot_a: "#tx-ov-rot-a", rot_b: "#tx-ov-rot-b" };
function abrirEditor(tipo, extra = {}) {
  const v = $("#leg-video"); v.pause();
  EDIT = { tipo, ...extra };
  let valor = "", info = "";
  if (tipo === "legenda") {
    const c = cartoes[EDIT.i], ps = c.palavras;
    valor = ps.map((p) => (p.e ? `*${p.w}*` : p.w)).join(" ");
    info = `${mmss(ps[0].start + descLeg())} → ${mmss(ps[ps.length - 1].end + descLeg())} · *palavra* destaca · tempo de cada palavra: ⏱ na lista ao lado`;
  } else if (tipo === "gancho") { valor = P.gancho.texto || ""; info = +P.gancho.ate ? `some aos ${P.gancho.ate} s (muda na lista ao lado)` : "fica o vídeo todo"; }
  else if (tipo === "nova") info = `começa em ${mmss(EDIT.t)} e dura até 2 s (ou até a próxima legenda)`;
  else { valor = P.comparacao?.[tipo === "rot_a" ? "rotulo_a" : "rotulo_b"] || ""; info = "vale para todos os trechos (cada trecho pode ter o seu na aba 2 · Cortes)"; }
  $("#tx-ed-titulo").textContent = TITULOS_ED[tipo];
  $("#tx-ed-texto").value = valor; $("#tx-ed-info").textContent = info;
  $("#tx-ed-excluir").hidden = tipo === "nova";
  const g = geometria(), ed = $("#tx-editor"), alvo = ALVO_ED[tipo] && $(ALVO_ED[tipo]);
  let top = g.oy + g.h * 0.5;
  if (alvo && !alvo.hidden) top = alvo.offsetTop + (tipo === "rot_a" ? 4 : alvo.offsetHeight + 6);
  ed.style.left = `${g.ox + 8}px`; ed.style.width = `${Math.max(g.w - 16, 240)}px`;
  ed.style.top = `${Math.max(4, Math.min(top, g.oy + g.h - 170))}px`;
  ed.hidden = false; $("#tx-ed-texto").focus(); $("#tx-ed-texto").select();
}
function fecharEditor() { $("#tx-editor").hidden = true; EDIT = null; }
function aplicarRespLegenda(r) {
  const { cartoes: c, indice, ...est } = r;
  P = est; cartoes = c; renderTudo(); renderListaCartoes(); desenharLegenda();
}
const desfazerLeg = { rotulo: "Desfazer", fn: () => tentar(desfazerLegendas) };
async function excluirCartao(i) {
  aplicarRespLegenda(await api("DELETE", `${base()}/legendas/cartao/${i}`));
  aviso(`Legenda ${i + 1} excluída.`, false, desfazerLeg);
}
$("#tx-editor").onsubmit = (e) => { e.preventDefault(); tentar(async () => {
  const E = EDIT; if (!E) return;
  const txt = $("#tx-ed-texto").value.trim(), chave = E.tipo === "rot_a" ? "rotulo_a" : "rotulo_b";
  if (E.tipo === "legenda") {
    if (!txt) { fecharEditor(); return excluirCartao(E.i); }
    aplicarRespLegenda(await api("PUT", `${base()}/legendas/cartao/${E.i}/texto`, { texto: txt })); aviso("Legenda salva.");
  } else if (E.tipo === "nova") {
    if (!txt) { fecharEditor(); return; }
    aplicarRespLegenda(await api("POST", `${base()}/legendas/cartao`, { texto: txt, ini: E.t, fim: Math.min(E.t + 2, P.duracao) }));
    aviso("Legenda adicionada.", false, desfazerLeg);
  } else if (E.tipo === "gancho") await salvarProjeto({ gancho: { texto: txt, ate: P.gancho.ate ?? 3 } });
  else await salvarProjeto({ comparacao: { [chave]: txt } });
  fecharEditor(); desenharLegenda();
}); };
$("#tx-ed-excluir").onclick = () => tentar(async () => {
  const E = EDIT; if (!E) return;
  fecharEditor();
  if (E.tipo === "legenda") return excluirCartao(E.i);
  if (E.tipo === "gancho") await salvarProjeto({ gancho: { texto: "", ate: P.gancho.ate ?? 3 } });
  else await salvarProjeto({ comparacao: { [E.tipo === "rot_a" ? "rotulo_a" : "rotulo_b"]: "" } });
  desenharLegenda(); aviso(E.tipo === "gancho" ? "Título tirado do vídeo." : "Rótulo tirado.", false, { rotulo: "Desfazer", fn: desfazer });
});
$("#tx-ed-cancelar").onclick = fecharEditor;
$("#tx-editor").addEventListener("keydown", (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fecharEditor(); } });
$("#leg-overlay").onclick = (e) => abrirEditor("legenda", { i: +e.currentTarget.dataset.i });
$("#tx-ov-gancho").onclick = () => abrirEditor("gancho");
$("#tx-ov-rot-a").onclick = () => abrirEditor("rot_a");
$("#tx-ov-rot-b").onclick = () => abrirEditor("rot_b");
function novaLegendaEm(t) {
  if (!P.segmentos.length) throw new Error("monte a timeline (aba 2 · Cortes) antes de escrever legendas");
  const i = cartaoNoInstante(t);
  if (i >= 0) { aviso("Já tem legenda neste instante: abrindo ela para editar."); return abrirEditor("legenda", { i }); }
  if (t > P.duracao - 0.2) throw new Error("esse instante é o fim do vídeo: volte um pouco");
  abrirEditor("nova", { t: Math.round(t * 100) / 100 });
}
$("#tx-add-aqui").onclick = () => tentar(async () => {
  if (!$("#leg-video").videoHeight) throw new Error("gere a prévia primeiro (botão acima) para escolher o instante no vídeo");
  novaLegendaEm($("#leg-video").currentTime);
});
$("#tx-add").onclick = () => tentar(async () => {        // depois da última legenda (ou no instante do vídeo, se estiver pausado nele)
  const v = $("#leg-video");
  const ult = cartoes.length ? cartoes[cartoes.length - 1].palavras.at(-1).end + descLeg() + 0.15 : 0;
  const t = v.videoHeight && v.currentTime > 0 && cartaoNoInstante(v.currentTime) < 0 ? v.currentTime : ult;
  if (t > P.duracao - 0.2) throw new Error("não há espaço depois da última legenda: leve o vídeo até um ponto livre e use “+ Legenda aqui”");
  if (v.videoHeight) v.currentTime = t;
  novaLegendaEm(t);
});
$("#leg-destacar").onclick = () => tentar(async () => {
  const r = await api("POST", `${base()}/legendas/destacar`);
  await carregarCartoes(); desenharLegenda();
  aviso(r.marcadas ? `${r.marcadas} palavra(s) destacada(s). Ajuste com *palavra* no texto de cada cartão.` : "Nada novo para destacar (cartões que você já destacou não mudam).");
});
["play", "pause", "seeked", "ratechange", "timeupdate"].forEach((ev) => $("#player-proxy").addEventListener(ev, sincronizarNarracao));
$("#com-narracao").onchange = sincronizarNarracao;
$("#gerar-proxy").onclick = () => tentar(async () => {
  await acompanhar(await api("POST", `${base()}/proxy`), "#tarefa-proxy");
  await recarregar(); aviso("Prévia pronta. Coloque o fone e grave.");
});
$("#salvar-roteiro").onclick = () => tentar(async () => { await salvarProjeto({ roteiro: $("#roteiro").value }); aviso("Roteiro salvo."); });
$("#narr-atual").onclick = (e) => tentar(async () => {
  if (e.target.id !== "remover-narr" || !confirm("Remover a narração do projeto?")) return;
  P = await api("DELETE", `${base()}/narracao`); renderTudo();
});

async function prepararMic() {
  if (streamMic) return;
  try {
    const id = $("#mic").value;
    streamMic = await navigator.mediaDevices.getUserMedia({ audio: {
      deviceId: id ? { exact: id } : undefined, channelCount: 1,
      echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    const devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "audioinput");
    const atual = streamMic.getAudioTracks()[0].getSettings().deviceId;
    $("#mic").innerHTML = devs.map((d) => `<option value="${d.deviceId}" ${d.deviceId === atual ? "selected" : ""}>${esc(d.label || "microfone")}</option>`).join("");
    const ctx = new AudioContext(); analisador = ctx.createAnalyser(); analisador.fftSize = 1024;
    ctx.createMediaStreamSource(streamMic).connect(analisador);
    const buf = new Float32Array(analisador.fftSize);
    (function medir() {
      analisador.getFloatTimeDomainData(buf);
      const pico = buf.reduce((m, x) => Math.max(m, Math.abs(x)), 0), db = 20 * Math.log10(pico + 1e-9);
      const n = $("#nivel"); n.style.width = Math.min(100, Math.max(0, (db + 60) / 60 * 100)) + "%";
      n.style.background = db > -3 ? "var(--rosa)" : db > -12 ? "var(--acento)" : "var(--verde)";
      requestAnimationFrame(medir);
    })();
  } catch (e) { aviso("Não consegui acessar o microfone: " + e.message, true); }
}
$("#mic").onchange = () => { streamMic?.getTracks().forEach((t) => t.stop()); streamMic = null; prepararMic(); };
// o navegador so pede o microfone quando o usuario clica (nada de permissao surpresa ao abrir a aba)
$("#mic-ativar").onclick = () => tentar(async () => {
  await prepararMic();
  if (streamMic) { $("#mic-ativar").textContent = "🎙 Microfone ativo"; $("#mic-ativar").disabled = true; }
});

function rolarTeleprompter() {
  const v = $("#player-proxy"), ta = $("#roteiro");
  if ($("#rolagem").checked && v.duration) ta.scrollTop = (v.currentTime / v.duration) * (ta.scrollHeight - ta.clientHeight);
}
function iniciarRelogio() {
  t0 = performance.now(); clearInterval(relogio);
  relogio = setInterval(() => { $("#rel-grav").textContent = mmss((performance.now() - t0) / 1000); rolarTeleprompter(); }, 100);
}
function estadoBotoes(rodando) { $("#ensaiar").disabled = $("#gravar").disabled = rodando; $("#parar").disabled = !rodando; }

$("#ensaiar").onclick = () => tentar(async () => {
  if (!P.tem_proxy) throw new Error("gere a prévia da montagem primeiro");
  const v = $("#player-proxy"); v.currentTime = 0; await v.play(); estadoBotoes(true); iniciarRelogio();
});
$("#gravar").onclick = () => tentar(async () => {
  if (!P.tem_proxy) throw new Error("gere a prévia da montagem primeiro");
  if (!P.proxy_atual && !confirm("A prévia é de uma versão antiga da montagem: a narração pode sair fora de sincronia com o vídeo final. Gravar mesmo assim?\n\n(Cancelar = clique em “Atualizar a prévia” antes.)")) return;
  await prepararMic(); if (!streamMic) return;
  audioSync.pause(); $("#com-narracao").checked = false;          // a narracao antiga nao pode vazar no microfone
  const v = $("#player-proxy"); v.pause(); v.currentTime = 0;
  for (const n of ["3", "2", "1"]) { $("#rel-grav").textContent = n; await new Promise((r) => setTimeout(r, 700)); }
  pedacos = [];
  const tipo = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "";
  gravador = new MediaRecorder(streamMic, { mimeType: tipo, audioBitsPerSecond: 256000 });
  gravador.ondataavailable = (e) => e.data.size && pedacos.push(e.data);
  gravador.onstop = () => {
    blobGravado = new Blob(pedacos, { type: gravador.mimeType || "audio/webm" });
    $("#audio-gravado").src = URL.createObjectURL(blobGravado);
    $("#info-grav").textContent = `${((performance.now() - t0) / 1000).toFixed(1)} s gravados`;
    $("#pos-gravacao").hidden = false;
  };
  gravador.onstart = () => { v.play(); iniciarRelogio(); };  // vídeo e voz começam juntos
  gravador.start(250);
  estadoBotoes(true);
  $("#rel-grav").style.color = "var(--rosa)";
});
$("#parar").onclick = () => {
  $("#player-proxy").pause(); clearInterval(relogio); estadoBotoes(false); $("#rel-grav").style.color = "";
  if (gravador && gravador.state !== "inactive") gravador.stop();
};
$("#player-proxy").addEventListener("ended", () => { if (gravador?.state === "recording") aviso("Fim do vídeo — termine a frase e clique em Parar."); });
$("#salvar-narr").onclick = () => tentar(async () => {
  if (!blobGravado) return;
  const fd = new FormData(); fd.append("arquivo", blobGravado, "narracao.webm");
  P = await api("POST", `${base()}/narracao`, fd); renderTudo();
  $("#pos-gravacao").hidden = true; blobGravado = null;
  aviso("Narração salva. Próximo passo: 6 · Textos → Transcrever.");
});
$("#descartar-narr").onclick = () => { blobGravado = null; $("#pos-gravacao").hidden = true; };
$("#narr-enviar").onclick = () => tentar(async () => {
  const f = $("#narr-arquivo").files[0]; if (!f) throw new Error("escolha um arquivo de áudio");
  const fd = new FormData(); fd.append("arquivo", f, f.name);
  P = await api("POST", `${base()}/narracao`, fd); renderTudo(); aviso("Narração enviada.");
});

// ------------------------------------------------------------------ 5 LEGENDAS
let cartoes = [];
async function carregarCartoes() {
  cartoes = await api("GET", `${base()}/legendas`);
  renderListaCartoes(); desenharLegenda();
}
function renderListaCartoes() {
  const d = descLeg();          // a lista mostra o tempo do VÍDEO (o mesmo do player)
  $("#lista-cartoes").innerHTML = cartoes.map((c, i) => {
    const ps = c.palavras;
    return `<div class="cartao-leg-bloco"><div class="cartao-leg"><span class="t">${mmss(ps[0].start + d)} → ${mmss(ps[ps.length - 1].end + d)}</span>
      <input data-i="${i}" aria-label="Texto do cartão ${i + 1}" value="${esc(ps.map((p) => (p.e ? `*${p.w}*` : p.w)).join(" "))}">
      <button class="mini" data-ouvir="${i}" title="levar o vídeo até este cartão e tocar" aria-label="Tocar o cartão ${i + 1} no vídeo">▶</button>
      <button class="mini" data-tempos="${i}" title="ajustar o tempo de cada palavra" aria-label="Ajustar o tempo das palavras do cartão ${i + 1}">⏱</button>
      <button class="mini" data-excluir-cartao="${i}" title="excluir este cartão (dá para desfazer)" aria-label="Excluir o cartão ${i + 1}">✕</button></div>
      <div class="tempos" data-painel-tempos="${i}" hidden></div></div>`;
  }).join("") || `<p class="dica">Nenhuma legenda. Transcreva a fala (acima) ou escreva a sua com “+ Adicionar legenda” / “+ Legenda aqui”.</p>`;
  $("#tx-n").textContent = cartoes.length ? `· ${cartoes.length} ${cartoes.length === 1 ? "cartão" : "cartões"}` : "";
  $("#tx-excluir-todas").disabled = $("#salvar-legendas").disabled = $("#leg-destacar").disabled = !cartoes.length;
  $("#baixar-srt").href = `${base()}/legendas.srt`;
  $("#baixar-vtt").href = `${base()}/legendas.vtt`;
  $("#leg-origem").value = P.legenda_origem === "video" ? "video" : "narracao";
}
// título do início, rótulos e aviso de legenda invisível (redesenhados com o projeto)
let SUGESTAO_GANCHO = "";
function renderTextos() {
  if (document.activeElement !== $("#tx-gancho")) $("#tx-gancho").value = P.gancho.texto || "";
  $("#tx-gancho-ate").value = P.gancho.ate ?? 3;
  $("#tx-gancho-tirar").disabled = !P.gancho.texto;
  const sug = SUGESTAO_GANCHO && SUGESTAO_GANCHO !== P.gancho.texto ? SUGESTAO_GANCHO : "";
  $("#tx-gancho-sugestao").hidden = !sug; $("#tx-gancho-sugestao").textContent = `Usar sugestão: “${sug}”`;
  const comp = P.layout === "comparacao" && P.tipo !== "longo";
  $("#tx-rotulos").hidden = !comp;
  if (comp) {
    if (document.activeElement !== $("#tx-rot-a")) $("#tx-rot-a").value = P.comparacao?.rotulo_a || "";
    if (document.activeElement !== $("#tx-rot-b")) $("#tx-rot-b").value = P.comparacao?.rotulo_b || "";
  }
  $("#tx-invisivel").hidden = !P.legendas_invisiveis;
  if ($("#lista-cartoes").childElementCount) renderListaCartoes();   // tempos dependem do deslocamento atual
  desenharLegenda();
}
const salvarGancho = (texto) => tentar(() => salvarProjeto({ gancho: { texto, ate: Math.max(0, +$("#tx-gancho-ate").value || 0) } }));
$("#tx-gancho").onchange = (e) => salvarGancho(e.target.value.trim());
$("#tx-gancho-ate").onchange = () => salvarGancho(P.gancho.texto || "");
$("#tx-gancho-tirar").onclick = () => tentar(async () => {
  await salvarProjeto({ gancho: { texto: "", ate: P.gancho.ate ?? 3 } });
  aviso("Título tirado do vídeo.", false, { rotulo: "Desfazer", fn: desfazer });
});
$("#tx-gancho-sugestao").onclick = () => salvarGancho(SUGESTAO_GANCHO);
$("#tx-rot-a").onchange = (e) => tentar(() => salvarProjeto({ comparacao: { rotulo_a: e.target.value.trim() } }));
$("#tx-rot-b").onchange = (e) => tentar(() => salvarProjeto({ comparacao: { rotulo_b: e.target.value.trim() } }));
$("#tx-mostrar").onclick = () => tentar(async () => {
  aplicarRespLegenda(await api("POST", `${base()}/legendas/manual`));
  aviso("Pronto: as legendas agora usam o tempo do vídeo e aparecem no render.", false, desfazerLeg);
});
$("#tx-excluir-todas").onclick = () => tentar(async () => {
  const n = cartoes.length;
  aplicarRespLegenda(await api("DELETE", `${base()}/legendas`));
  aviso(`${n} legenda(s) excluída(s).`, false, desfazerLeg);
});

// ------------------------------------------------ presets por plataforma + visual
let PLATS = null;
async function renderPlataformas() {
  if (!PLATS) PLATS = await api("GET", "/api/legendas/plataformas");
  const L = P.legenda;
  $("#botoes-plataforma").innerHTML = Object.entries(PLATS.plataformas).map(([id, p]) =>
    `<button data-plat="${id}" class="${L.plataforma === id ? "primario" : ""}" title="${esc(p.nota)}">${esc(p.nome)}</button>`).join("");
  const nota = L.plataforma && PLATS.plataformas[L.plataforma];
  if (nota) $("#nota-plataforma").textContent = `${nota.nome}: ${nota.nota} (recomendação, não regra oficial; ajuste à vontade)`;
  $("#lv-fonte").innerHTML = PLATS.fontes.map((f) => `<option ${f === (L.fonte || "Arial Black") ? "selected" : ""}>${f}</option>`).join("");
  $("#lv-tamanho").value = L.tamanho ?? ""; $("#lv-contorno").value = L.contorno ?? ""; $("#lv-sombra").value = L.sombra ?? "";
  $("#lv-tamanho").placeholder = $("#lv-contorno").placeholder = $("#lv-sombra").placeholder = "padrão";
  $("#lv-cor").value = L.cor || "#ffffff"; $("#lv-destaque").value = L.destaque || "#ffde00";
  $("#lv-animacao").value = L.animacao || "nenhuma";
}
$("#botoes-plataforma").onclick = (e) => tentar(async () => {
  const id = e.target.dataset.plat; if (!id) return;
  const antes = fotografia();
  P = await api("POST", `${base()}/legendas/plataforma/${id}`);
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  renderTudo(); await carregarCartoes(); await renderPlataformas();
  aviso(`Preset ${PLATS.plataformas[id].nome} aplicado. Gere quadros (aba 7) para conferir.`);
});
$("#lv-salvar").onclick = () => tentar(async () => {
  const n = (id) => ($(id).value === "" ? null : +$(id).value);
  await salvarProjeto({ legenda: { fonte: $("#lv-fonte").value, tamanho: n("#lv-tamanho"), contorno: n("#lv-contorno"), sombra: n("#lv-sombra"),
    cor: $("#lv-cor").value, destaque: $("#lv-destaque").value, animacao: $("#lv-animacao").value } });
  await renderPlataformas(); aviso("Visual da legenda salvo.");
});

// ------------------------------------------------ tempo por palavra
let audioNarr = null;
function ouvirTrecho(ini, fim) {
  if (!P.narracao) throw new Error("o projeto não tem narração");
  if (!audioNarr) audioNarr = new Audio();
  const src = arq(P.narracao).split("&t=")[0];
  if (!audioNarr.src.includes(encodeURIComponent(P.narracao))) audioNarr.src = src;
  audioNarr.currentTime = Math.max(ini - 0.05, 0); audioNarr.play().catch(() => {});
  clearTimeout(ouvirTrecho.t); ouvirTrecho.t = setTimeout(() => audioNarr.pause(), (fim - ini + 0.15) * 1000);
}
$("#lista-cartoes").addEventListener("click", (e) => tentar(async () => {
  const d = e.target.dataset;
  if (d.excluirCartao != null) return excluirCartao(+d.excluirCartao);
  if (d.ouvir != null) {
    const ps = cartoes[+d.ouvir].palavras, v = $("#leg-video");
    if (!v.videoHeight) return ouvirTrecho(ps[0].start, ps[ps.length - 1].end);   // sem prévia: só a narração
    v.currentTime = ps[0].start + descLeg(); v.play().catch(() => {});
    clearTimeout(ouvirTrecho.t); ouvirTrecho.t = setTimeout(() => v.pause(), (ps[ps.length - 1].end - ps[0].start + 0.2) * 1000);
    v.scrollIntoView({ block: "nearest", behavior: "smooth" }); return;
  }
  if (d.tempos != null) {
    const painel = $(`[data-painel-tempos="${d.tempos}"]`); painel.hidden = !painel.hidden;
    if (!painel.hidden) painel.innerHTML = cartoes[+d.tempos].palavras.map((p, j) => `<div class="linha palavra-t" data-j="${j}">
      <input class="w" aria-label="Palavra ${j + 1}" value="${esc(p.w)}" size="12"><label>de <input type="number" step="0.01" class="s" value="${p.start}"></label>
      <label>até <input type="number" step="0.01" class="e" value="${p.end}"></label>
      <button class="mini" data-ouvir-p="${j}" title="ouvir a palavra" aria-label="Ouvir a palavra ${j + 1}">▶</button>
      <span class="dica">início</span><button class="mini" data-nudge="-0.05" title="começa 50 ms antes" aria-label="Começar 50 ms antes">−</button><button class="mini" data-nudge="0.05" title="começa 50 ms depois" aria-label="Começar 50 ms depois">+</button></div>`).join("") +
      `<div class="linha"><button class="primario" data-salvar-tempos="${d.tempos}">Salvar tempos</button><span class="dica">Tempos no relógio ${descLeg() ? "da narração (sem o deslocamento da trilha)" : P.legenda_origem === "narracao" ? "da narração" : "do vídeo"}. − / + ajustam o início da palavra em 50 ms; o fim é editável no campo.</span></div>`;
    return;
  }
  const painel = e.target.closest("[data-painel-tempos]"); if (!painel) return;
  const i = +painel.dataset.painelTempos, linha = e.target.closest(".palavra-t");
  if (d.ouvirP != null) return ouvirTrecho(+linha.querySelector(".s").value, +linha.querySelector(".e").value);
  if (d.nudge) { const s = linha.querySelector(".s"), e2 = linha.querySelector(".e"); s.value = Math.min(+s.value + +d.nudge, +e2.value - 0.05).toFixed(2); return; }
  if (d.salvarTempos != null) {
    const palavras = [...painel.querySelectorAll(".palavra-t")].map((l) => ({ w: l.querySelector(".w").value.trim(), start: +l.querySelector(".s").value, end: +l.querySelector(".e").value }));
    cartoes = await api("PUT", `${base()}/legendas/cartao/${i}`, { palavras });
    await carregarCartoes(); await recarregar(); aviso("Tempos salvos.");
  }
}));
// gerar / atualizar: a versao de antes fica guardada no servidor (Desfazer troca de volta)
async function gerarLegendas(origem, atualizar) {
  const tinha = cartoes.length;
  const r = await acompanhar(await api("POST", `${base()}/legendas/transcrever`, { modelo: $("#modelo-whisper").value, origem }), "#tarefa-leg");
  await carregarCartoes(); await recarregar();
  const fora = r.fora_do_video ? ` ${r.fora_do_video} palavra(s) depois do fim do vídeo ficaram de fora.` : "";
  aviso(`${atualizar ? "Legendas atualizadas" : "Legendas geradas"}: ${r.cartoes} cartões.${fora}`, false,
    tinha ? { rotulo: "Desfazer", fn: () => tentar(desfazerLegendas) } : null);
}
async function desfazerLegendas() {
  const r = await api("POST", `${base()}/legendas/restaurar`);
  await carregarCartoes(); P = r; renderTudo(); aviso("Legendas de antes de volta (clique de novo em Desfazer para refazer).", false, { rotulo: "Desfazer", fn: () => tentar(desfazerLegendas) });
}
const atualizarLegendas = () => tentar(() => gerarLegendas(cartoes.length && P.legenda_origem !== "manual" ? P.legenda_origem || "narracao" : $("#leg-origem").value, cartoes.length > 0));
$("#transcrever").onclick = () => tentar(() => gerarLegendas($("#leg-origem").value, false));
$("#leg-atualizar").onclick = atualizarLegendas;
$("#leg-alerta-atualizar").onclick = atualizarLegendas;
function renderAlertaLegenda() {
  const motivos = [];
  if (P.legendas_desatualizadas) motivos.push(P.legenda_origem === "video" ? "a montagem mudou depois que as legendas foram feitas" : "a narração mudou depois que as legendas foram feitas");
  if (P.legendas_passam > 0) motivos.push(`a legenda passa ${P.legendas_passam.toFixed(1)} s do fim do vídeo (no vídeo ela é cortada no fim)`);
  $("#leg-alerta").hidden = !motivos.length;
  if (motivos.length) $("#leg-alerta-texto").textContent = "Atenção: " + motivos.join("; ") + ". ";
  $("#leg-atualizar").disabled = !P.n_cartoes || P.legenda_origem === "manual";
  $("#leg-atualizar").title = P.legenda_origem === "manual" ? "Legendas escritas à mão não são transcritas: use Transcrever para trocar por uma transcrição" : $("#leg-atualizar").title;
  renderTextos();
}
$("#salvar-legendas").onclick = () => tentar(async () => {
  const textos = $$("#lista-cartoes .cartao-leg > input").map((i) => i.value);   // so o texto do cartao (nao os campos de tempo)
  const apagados = textos.filter((t) => !t.trim()).length;
  await api("PUT", `${base()}/legendas`, { textos });
  await carregarCartoes(); await recarregar();
  aviso(apagados ? `Legendas salvas; ${apagados} cartão(ões) vazio(s) excluído(s).` : "Legendas salvas.", false, apagados ? desfazerLeg : null);
});
