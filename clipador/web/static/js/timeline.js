// Clipador - timeline de video e reproducao continua (dois players).
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------ timeline de video (aba 2)
let cursorV = 0, tocandoTL = false, tlvArraste = null;
const pxs = () => +$("#tlv-zoom").value;                       // pixels por segundo
const inicioDo = (i) => P.segmentos.slice(0, i).reduce((a, s) => a + s.fim - s.ini, 0);

function miniaturaDe(s) {
  const f = P.fontes.find((x) => x.id === s.fonte); if (!f) return "";
  const meio = (s.ini + s.fim) / 2;
  const c = (f.cenas || []).find((c) => c.ini <= meio && meio < c.fim) || (f.cenas || [])[0];
  return c && c.miniatura ? `${base()}/arquivo?caminho=${encodeURIComponent(c.miniatura)}` : "";
}

function renderTimelineVideo() {
  if (!P) return;
  const px = pxs(), T = P.duracao, largura = Math.max(T * px + 40, 300);
  const passo = px >= 120 ? 1 : px >= 40 ? 2 : px >= 20 ? 5 : 10;
  let regua = "";
  for (let t = 0; t <= T + 0.001; t += passo) regua += `<span style="left:${t * px}px">${mmss(t).replace(".0", "")}</span>`;
  let acc = 0;
  const blocos = P.segmentos.map((s, i) => {
    const d = s.fim - s.ini, x = acc * px; acc += d;
    const img = miniaturaDe(s);
    return `<div class="tlv-bloco ${i === segSel ? "sel" : ""}" data-i="${i}" style="left:${x}px;width:${Math.max(d * px - 2, 6)}px;${img ? `background-image:url('${img}')` : ""}"
      title="T${i + 1}: ${s.congelado ? `quadro congelado em ${mmss(s.ini)} da fonte por ${d.toFixed(2)} s` : `${mmss(s.ini)}–${mmss(s.fim)} da fonte (${d.toFixed(2)} s)`}${s.loop ? " · loop: repete o começo" : ""}">
      <i class="alca ini" data-alca="ini"></i><span>${s.loop ? "↻ " : ""}${s.congelado ? "❄ " : ""}T${i + 1} · ${d.toFixed(1)}s${s.rotulo ? " · " + esc(s.rotulo) : ""}</span><i class="alca fim" data-alca="fim"></i></div>`;
  }).join("");
  $("#tlv").innerHTML = `<div class="tlv-trilho" style="width:${largura}px">
    <div class="tlv-regua">${regua}</div><div class="tlv-pista">${blocos || `<span class="tl-vazio">sem trechos — clique nas cenas abaixo ou use Sugerir cortes</span>`}</div>
    <div id="tlv-cursor" style="left:${cursorV * px}px"></div><div id="tlv-insercao" hidden></div></div>`;
  atualizarTempoTL();
}
function atualizarTempoTL() {
  $("#tlv-tempo").textContent = `${mmss(cursorV)} / ${mmss(P?.duracao || 0)}`;
  const c = $("#tlv-cursor"); if (c) c.style.left = cursorV * pxs() + "px";
}
$("#tlv-zoom").oninput = renderTimelineVideo;

async function opTimeline(corpo, msg) {
  pararTimeline();
  const antes = fotografia();
  const r = await api("POST", `${base()}/timeline`, corpo);
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  P = r; segSel = r.selecionado ?? -1; renderTudo();
  if (msg) aviso(msg);
}
const dividirNoCursor = () => tentar(() => opTimeline({ op: "dividir_no_tempo", t: +cursorV.toFixed(3) }, "Dividido no cursor."));
const duplicarSel = () => tentar(() => { if (segSel < 0) throw new Error("selecione um trecho"); return opTimeline({ op: "duplicar", i: segSel }); });
const removerSel = () => tentar(() => { if (segSel < 0) throw new Error("selecione um trecho"); return opTimeline({ op: "remover", i: segSel }); });
$("#tlv-dividir").onclick = dividirNoCursor; $("#tlv-duplicar").onclick = duplicarSel; $("#tlv-remover").onclick = removerSel;
$("#tlv-loop").onclick = () => tentar(() => opTimeline({ op: "fechar_loop" }, "Loop fechado: o fim repete 0,9 s do começo (Ctrl+Z desfaz)."));
$("#tlv-congelar").onclick = () => tentar(() => opTimeline({ op: "congelar", t: +cursorV.toFixed(3) },
  "Quadro congelado por 1 s no cursor (som do jogo mudo nele). Puxe a borda para mudar a duração."));

// clique, arrastar para reordenar e aparar pelas alcas (pointer events: mouse, caneta e toque)
$("#tlv").addEventListener("pointerdown", (e) => {
  const trilho = e.target.closest(".tlv-trilho"); if (!trilho) return;
  const x0 = e.clientX, r = trilho.getBoundingClientRect();
  const bloco = e.target.closest(".tlv-bloco"), alca = e.target.dataset.alca;
  const t = Math.max(0, Math.min(P.duracao, (e.clientX - r.left) / pxs()));
  if (!bloco) { cursorV = t; atualizarTempoTL(); return; }
  const i = +bloco.dataset.i;
  segSel = i; cursorV = t; atualizarTempoTL();
  $$(".tlv-bloco").forEach((b) => b.classList.toggle("sel", +b.dataset.i === i));
  $$("#lista-segmentos li").forEach((li) => li.classList.toggle("sel", +li.dataset.i === i));
  tlvArraste = { i, alca, x0, moveu: false, bloco, larg0: bloco.offsetWidth, left0: bloco.offsetLeft };
  bloco.setPointerCapture(e.pointerId);
});
$("#tlv").addEventListener("pointermove", (e) => {
  const a = tlvArraste; if (!a) return;
  const dx = e.clientX - a.x0; if (Math.abs(dx) > 4) a.moveu = true; if (!a.moveu) return;
  const s = P.segmentos[a.i], px = pxs();
  if (a.alca === "fim") {
    a.bloco.style.width = Math.max(a.larg0 + dx, 6) + "px";
    a.bloco.title = `fim: ${mmss(s.fim + dx / px)}`;
  } else if (a.alca === "ini") {
    a.bloco.style.left = a.left0 + dx + "px"; a.bloco.style.width = Math.max(a.larg0 - dx, 6) + "px";
    a.bloco.title = `início: ${mmss(s.ini + dx / px)}`;
  } else {
    a.bloco.style.transform = `translateX(${dx}px)`; a.bloco.classList.add("arrastando");
    const xPonteiro = e.clientX - $(".tlv-trilho").getBoundingClientRect().left;   // solta onde o ponteiro esta
    const destino = alvoReordenar(xPonteiro);
    const ins = $("#tlv-insercao"); ins.hidden = false; ins.style.left = inicioDo(destino > a.i ? destino + 1 : destino) * px + "px";
    a.destino = destino;
  }
});
$("#tlv").addEventListener("pointerup", (e) => {
  const a = tlvArraste; tlvArraste = null; if (!a || !a.moveu) return;
  const dx = e.clientX - a.x0, s = P.segmentos[a.i], ima = $("#tlv-ima").checked ? 0.25 : 0;
  if (a.alca === "fim") tentar(() => opTimeline({ op: "aparar", i: a.i, fim: +(s.fim + dx / pxs()).toFixed(3), ima }));
  else if (a.alca === "ini") tentar(() => opTimeline({ op: "aparar", i: a.i, ini: +(s.ini + dx / pxs()).toFixed(3), ima }));
  else if (a.destino != null && a.destino !== a.i) tentar(() => opTimeline({ op: "mover", i: a.i, para: a.destino }));
  else renderTimelineVideo();
});
function alvoReordenar(xCentro) {
  const t = xCentro / pxs(); let acc = 0;
  for (let k = 0; k < P.segmentos.length; k++) {
    const d = P.segmentos[k].fim - P.segmentos[k].ini;
    if (t < acc + d / 2) return k;
    acc += d;
  }
  return P.segmentos.length - 1;
}

// reproducao continua da montagem usando o player da fonte
function segAtual() {
  let acc = 0;
  for (let i = 0; i < P.segmentos.length; i++) {
    const d = P.segmentos[i].fim - P.segmentos[i].ini;
    if (cursorV < acc + d - 0.02) return { i, dentro: cursorV - acc, acc };
    acc += d;
  }
  return null;
}
// ---- reproducao continua da montagem: dois players alternados. Com um so, o corte "pulava" (currentTime) e o
// navegador decodificava desde o quadro-chave: ~0,2 s de trava + 0,2 s tocando alem do corte (timeupdate e lento).
// Agora o proximo trecho ja fica posicionado no outro player e o corte so troca qual esta visivel.
const playerA = () => $("#player-fonte"), playerB = () => $("#player-fonte-b");
let tlAtivo = null, tlPrep = null, tlRaf = 0, tlTimer = 0, tlTick = 0;
const mostrarPlayer = (el) => {
  playerA().classList.toggle("tl-oculto", el !== playerA());
  playerB().classList.toggle("tl-oculto", el !== playerB());
};
function prepararPlayer(v, seg) {      // deixa `v` parado no 1o quadro de `seg`, com dados para tocar sem travar
  return new Promise((ok) => {
    const url = `${base()}/fontes/${seg.fonte}/video`;
    let feito = false;
    const fim = () => { if (!feito) { feito = true; ok(); } };
    setTimeout(fim, 2500);                                   // nunca prende a montagem esperando o navegador
    const buscar = () => {
      v.pause();
      const pronto = () => (v.readyState >= 3 ? fim() : v.addEventListener("canplay", fim, { once: true }));
      if (Math.abs(v.currentTime - seg.ini) < 0.03) return pronto();
      v.addEventListener("seeked", pronto, { once: true });
      v.currentTime = seg.ini;
    };
    if (v.src.endsWith(url)) buscar(); else { v.addEventListener("loadedmetadata", buscar, { once: true }); v.src = url; }
  });
}
// trechos vizinhos: nem precisa trocar de player (quadro congelado nunca emenda: ele fica parado)
const emendado = (s, n) => !s.congelado && !n.congelado && s.fonte === n.fonte && Math.abs(n.ini - s.fim) < 0.05;
let tlParado = 0;            // quadro congelado: o relogio e o da pagina (performance.now), o video fica pausado
const segurarQuadro = (dentro = 0) => { tlParado = performance.now() - dentro * 1000; };
function prepararProximo() {
  const prox = tocandoTL.i + 1;
  if (prox >= P.segmentos.length || emendado(P.segmentos[tocandoTL.i], P.segmentos[prox])) { tlPrep = null; return; }
  const reg = { el: tlAtivo === playerA() ? playerB() : playerA(), i: prox, pronto: false };
  reg.p = prepararPlayer(reg.el, P.segmentos[prox]).then(() => { reg.pronto = true; });
  tlPrep = reg;
}
async function tocarTimeline() {
  if (!P.segmentos.length) return;
  if (cursorV >= P.duracao - 0.05) cursorV = 0;
  const atual = segAtual(); if (!atual) return;
  const s = P.segmentos[atual.i], A = playerA();
  if ($("#cortes-fonte").value !== s.fonte) { $("#cortes-fonte").value = s.fonte; carregarFonteNoPlayer();
    await new Promise((r) => A.addEventListener("loadedmetadata", r, { once: true })); }
  tlAtivo = A; mostrarPlayer(A);
  tocandoTL = { i: atual.i, acc: atual.acc };
  if (s.congelado) { A.currentTime = s.ini; segurarQuadro(atual.dentro); }
  else { A.currentTime = s.ini + atual.dentro; await A.play().catch(() => {}); }
  $("#tlv-play").textContent = "⏸";
  prepararProximo();
  agendarTL();
}
// roda a cada quadro da tela (corte no instante certo; timeupdate so dispara ~4x/s). Com a aba/janela oculta o
// requestAnimationFrame para de vez, entao um setTimeout de seguranca garante que o corte nao fique sem vigia.
function agendarTL() {
  cancelAnimationFrame(tlRaf); clearTimeout(tlTimer);
  tlRaf = requestAnimationFrame(vigiarTL); tlTimer = setTimeout(vigiarTL, 100);
}
function vigiarTL() {
  cancelAnimationFrame(tlRaf); clearTimeout(tlTimer);
  if (!tocandoTL) return;
  const v = tlAtivo, s = P.segmentos[tocandoTL.i];
  if (!s) return pararTimeline();
  const dentro = s.congelado ? (performance.now() - tlParado) / 1000 : Math.max(v.currentTime - s.ini, 0);
  cursorV = tocandoTL.acc + Math.min(dentro, s.fim - s.ini);
  if ((tlTick++ & 3) === 0) atualizarTempoTL();              // cursor e relogio ~15x/s, nao a cada quadro
  if (dentro >= s.fim - s.ini - 0.03 || (!s.congelado && v.ended)) { avancarTL(); return; }
  agendarTL();
}
async function avancarTL() {
  const s = P.segmentos[tocandoTL.i], prox = tocandoTL.i + 1, acc = tocandoTL.acc + (s.fim - s.ini);
  if (prox >= P.segmentos.length) { cursorV = P.duracao; pararTimeline(); atualizarTempoTL(); return; }
  const n = P.segmentos[prox], velho = tlAtivo;
  if (emendado(s, n)) { tocandoTL = { i: prox, acc }; prepararProximo(); agendarTL(); return; }
  const novo = velho === playerA() ? playerB() : playerA();
  tocandoTL = { i: prox, acc };
  const preparado = tlPrep && tlPrep.i === prox && tlPrep.el === novo;
  if (!preparado) { velho.pause(); await prepararPlayer(novo, n); }
  else if (!tlPrep.pronto) { velho.pause(); await tlPrep.p; }
  if (!tocandoTL || tocandoTL.i !== prox) return;            // o usuario parou enquanto o navegador preparava
  if (n.congelado) segurarQuadro(); else novo.play().catch(() => {});
  mostrarPlayer(novo); velho.pause(); tlAtivo = novo;
  prepararProximo(); agendarTL();
}
function pararTimeline() {
  if (!tocandoTL) return;
  cancelAnimationFrame(tlRaf); clearTimeout(tlTimer);
  const A = playerA(), B = playerB(), ativo = tlAtivo || A, s = P.segmentos[tocandoTL.i];
  tocandoTL = false; tlPrep = null;
  A.pause(); B.pause();
  if (ativo !== A) {                   // o player principal (com controles) volta a ser o visivel, onde o video parou
    const t = ativo.currentTime;
    if (s && $("#cortes-fonte").value !== s.fonte) { $("#cortes-fonte").value = s.fonte; carregarFonteNoPlayer();
      A.addEventListener("loadedmetadata", () => (A.currentTime = t), { once: true }); }
    else A.currentTime = t;
  }
  mostrarPlayer(A); $("#tlv-play").textContent = "▶";
}
$("#tlv-play").onclick = () => (tocandoTL ? pararTimeline() : tocarTimeline());

// arrastar e soltar arquivos: video vira fonte do projeto, audio vai para a biblioteca de musicas
window.addEventListener("dragover", (e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); document.body.classList.add("soltando"); } });
window.addEventListener("dragleave", (e) => { if (!e.relatedTarget) document.body.classList.remove("soltando"); });
window.addEventListener("drop", (e) => {
  if (!e.dataTransfer?.files?.length) return;
  e.preventDefault(); document.body.classList.remove("soltando");
  tentar(async () => {
    if (!P) throw new Error("abra ou crie um projeto antes de soltar arquivos");
    for (const f of e.dataTransfer.files) {
      const fd = new FormData(); fd.append("arquivo", f, f.name);
      if (f.type.startsWith("video/") || /\.(mp4|mov|mkv|webm|avi|m4v)$/i.test(f.name)) {
        $$("#abas button")[0].click(); $("#tarefa-fonte").textContent = `enviando ${f.name}…`;
        await aposFonte(await api("POST", `${base()}/fontes/upload`, fd));
      } else if (f.type.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|flac|aac|opus)$/i.test(f.name)) {
        const m = await api("POST", "/api/biblioteca/musicas/upload", fd); aviso(`"${m.nome}" foi para a biblioteca de músicas (aba 4).`);
      } else aviso(`"${f.name}" não é vídeo nem áudio; ignorado.`, true);
    }
  });
});
