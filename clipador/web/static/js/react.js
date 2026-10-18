// Clipador - aba React: composicao ao vivo, camera e gravacao.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------------ 9 REACT
let rsStream = null, rsRec = null, rsPedacos = [], rsBlob = null, rsT0 = 0, rsAcum = 0, rsRelogio = null, rsAnalisador = null;
let rsArraste = null;
const R_ = () => P.react;

const cfgPosicao = (R) => (R.modo === "fundo_virtual" ? R.recorte : R.janela);   // fundo virtual tem posicao propria
function geometriaJanela(stageW, stageH) {
  const R = R_(), J = R.janela, modo = R.modo, inf = R.info || { w: 16, h: 9 };
  if (modo === "dividido") return null;
  const C = cfgPosicao(R), larg = stageW * C.w;
  const forma = modo === "janela" ? J.forma : "retangulo";
  const alt = forma === "circulo" ? larg : forma === "vertical" ? larg * 16 / 9 : larg * inf.h / inf.w;
  return { larg, alt, left: Math.max(0, C.x * (stageW - larg)), top: Math.max(0, C.y * (stageH - alt)), forma };
}
function renderStageReact() {
  if (!P || $("[data-painel=react]").hidden && !renderStageReact.forcar) return;
  const R = R_(), longo = P.tipo === "longo", stage = $("#rs");
  stage.style.aspectRatio = longo ? "16 / 9" : "9 / 16";
  stage.style.width = longo ? "100%" : "min(100%, 320px)";
  stage.classList.toggle("dividido", R.modo === "dividido");
  const sw = stage.clientWidth, sh = stage.clientHeight, cam = $("#rs-cam");
  const fundo = $("#rs-fundo");
  if (P.tem_proxy) { if (!fundo.src.endsWith(urlProxy())) fundo.src = urlProxy(); $("#rs-vazio").hidden = true; }
  else { fundo.removeAttribute("src"); $("#rs-vazio").hidden = false; }
  const temCam = !!(rsStream || (R.arquivo && P.react_extra?.camera_ok));
  cam.hidden = !temCam;
  const v = $("#rs-video");
  if (!rsStream && R.arquivo) {          // gravacao: toca junto com o fundo (antes ficava em loop, solta do jogo)
    const src = `${base()}/arquivo?caminho=react/camera.mp4&v=${P.react_extra?.camera_versao}`;
    if (v.dataset.src !== src) { v.srcObject = null; v.dataset.src = src; v.src = src; v.loop = false; v.muted = true; }
  }
  v.style.transform = R.espelhar ? "scaleX(-1)" : "none";
  $("#rs-canvas").style.transform = R.espelhar ? "scaleX(-1)" : "none";
  if (R.modo === "dividido") {
    Object.assign(cam.style, { left: 0, top: "50%", width: "100%", height: "50%", borderRadius: 0, border: "none" });
  } else {
    const g = geometriaJanela(sw, sh);
    Object.assign(cam.style, { left: g.left + "px", top: g.top + "px", width: g.larg + "px", height: g.alt + "px",
      borderRadius: g.forma === "circulo" ? "50%" : "0", border: R.janela.borda && !R.chroma.ativo && g.forma !== "circulo" ? "2px solid #fff" : "none" });
  }
  cam.style.cursor = R.modo === "dividido" ? "default" : "move";
  rsUsarIA = !!(R.recorte_ia.ativo && P.react_extra?.matte_pronto && !rsStream && R.modo !== "dividido");
  const usarRecorte = (R.chroma.ativo || rsUsarIA) && R.modo !== "dividido";
  $("#rs-canvas").hidden = !usarRecorte; v.style.visibility = usarRecorte ? "hidden" : "visible"; cam.style.background = usarRecorte ? "transparent" : "#111";
  if (rsUsarIA) {
    const src = `${base()}/arquivo?caminho=react/matte.mp4&v=${P.react_extra.matte_versao}`;
    if (rsMatte.dataset.src !== src) { rsMatte.dataset.src = src; rsMatte.src = src; }
  }
  sincronizarStage(); comporReact(); garantirLoopStage();
}
// ---- composicao ao vivo: fundo (previa), camera e mascara da IA no MESMO instante; recorte com a conta do render
const rsMatte = Object.assign(document.createElement("video"), { muted: true, playsInline: true, preload: "auto" });
const rsAux = document.createElement("canvas");
let rsUsarIA = false, rsTocando = false, rsLoop = false;
function sincronizarStage() {
  const R = R_(), f = $("#rs-fundo"), v = $("#rs-video");
  if (!R || rsStream) return;                                          // camera ao vivo: nao ha o que alinhar
  const tc = f.currentTime - (+R.deslocamento || 0), dentro = tc >= 0 && tc <= (R.info?.dur || 0);
  $("#rs-cam").style.opacity = R.arquivo && !dentro && f.currentTime > 0 ? "0" : "1";
  for (const el of rsUsarIA ? [v, rsMatte] : [v]) {
    if (!el.src) continue;
    if (dentro && Math.abs(el.currentTime - tc) > 0.1) el.currentTime = tc;
    if (rsTocando && dentro) { if (el.paused) el.play().catch(() => {}); } else if (!el.paused) el.pause();
  }
  if (f.duration) $("#rs-pos").value = f.currentTime / f.duration;
}
function comporReact() {
  const R = R_(), v = $("#rs-video"), c = $("#rs-canvas");
  if (!R || c.hidden || !v.videoWidth) return;
  const box = $("#rs-cam").getBoundingClientRect();
  const w = Math.max(2, Math.min(360, Math.round(box.width))), h = Math.max(2, Math.round(w * v.videoHeight / v.videoWidth));
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  const g = c.getContext("2d", { willReadFrequently: true }); g.drawImage(v, 0, 0, w, h);
  const img = g.getImageData(0, 0, w, h), px = img.data, n = w * h, alfa = new Float32Array(n).fill(1);
  if (R.chroma.ativo) {
    // mesma conta do filtro chromakey do FFmpeg: distancia nos canais U/V (BT.601), media 3x3, rampa similaridade->mistura
    const hx = R.chroma.cor.slice(1), kr = parseInt(hx.slice(0, 2), 16), kg = parseInt(hx.slice(2, 4), 16), kb = parseInt(hx.slice(4, 6), 16);
    const ku = -0.1482 * kr - 0.2910 * kg + 0.4392 * kb + 128, kv = 0.4392 * kr - 0.3678 * kg - 0.0714 * kb + 128;
    const dif = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const r = px[4 * i], gg = px[4 * i + 1], b = px[4 * i + 2];
      const du = -0.1482 * r - 0.2910 * gg + 0.4392 * b + 128 - ku, dv = 0.4392 * r - 0.3678 * gg - 0.0714 * b + 128 - kv;
      dif[i] = Math.sqrt((du * du + dv * dv) / 130050);
    }
    const sim = R.chroma.similaridade, bl = R.chroma.mistura;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      let s = 0, k = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const yy = y + dy, xx = x + dx; if (yy >= 0 && yy < h && xx >= 0 && xx < w) { s += dif[yy * w + xx]; k++; }
      }
      const d = s / k; alfa[y * w + x] = bl > 0.0001 ? Math.min(Math.max((d - sim) / bl, 0), 1) : d > sim ? 1 : 0;
    }
  }
  if (rsUsarIA && rsMatte.videoWidth) {                                  // mascara real gerada pela IA (branco = pessoa)
    if (rsAux.width !== w || rsAux.height !== h) { rsAux.width = w; rsAux.height = h; }
    const ga = rsAux.getContext("2d", { willReadFrequently: true }); ga.drawImage(rsMatte, 0, 0, w, h);
    const md = ga.getImageData(0, 0, w, h).data;
    for (let i = 0; i < n; i++) alfa[i] *= md[4 * i] / 255;
  }
  for (let i = 0; i < n; i++) px[4 * i + 3] = Math.round(alfa[i] * 255);
  g.putImageData(img, 0, 0);
}
let rsRaf = 0, rsTimer = 0;
function garantirLoopStage() {      // por quadro; com a janela oculta o rAF congela, entao um setTimeout segura a sincronia
  if (rsLoop || !(rsTocando || rsStream) || $("[data-painel=react]").hidden) return;
  rsLoop = true;
  (function passo() {
    cancelAnimationFrame(rsRaf); clearTimeout(rsTimer);
    if (!(rsTocando || rsStream) || $("[data-painel=react]").hidden) { rsLoop = false; return; }
    sincronizarStage(); comporReact();
    rsRaf = requestAnimationFrame(passo); rsTimer = setTimeout(passo, 120);
  })();
}
$("#rs-tocar").onclick = () => {
  const f = $("#rs-fundo");
  if (!f.src) return aviso("Gere a prévia da montagem primeiro (botão abaixo da prévia).", true);
  rsTocando = !rsTocando;
  $("#rs-tocar").textContent = rsTocando ? "⏸ Pausar" : "▶ Tocar composição";
  if (rsTocando) { if (f.ended) f.currentTime = 0; f.play().catch(() => {}); garantirLoopStage(); } else { f.pause(); sincronizarStage(); }
};
$("#rs-pos").oninput = () => { const f = $("#rs-fundo"); if (f.duration) f.currentTime = +$("#rs-pos").value * f.duration; };
$("#rs-fundo").addEventListener("seeked", () => { sincronizarStage(); setTimeout(comporReact, 80); });
$("#rs-fundo").addEventListener("ended", () => { rsTocando = false; $("#rs-tocar").textContent = "▶ Tocar composição"; sincronizarStage(); });
$("#rs-video").addEventListener("seeked", () => comporReact());
rsMatte.addEventListener("seeked", () => comporReact());
new ResizeObserver(() => renderStageReact()).observe($("#rs"));

// arrastar a janela (so no modo janela)
$("#rs-cam").addEventListener("pointerdown", (e) => {
  if (R_().modo === "dividido") return;
  const stage = $("#rs").getBoundingClientRect(), cam = $("#rs-cam").getBoundingClientRect();
  rsArraste = { dx: e.clientX - cam.left, dy: e.clientY - cam.top, sw: stage.width, sh: stage.height, cw: cam.width, ch: cam.height, l: stage.left, t: stage.top };
  $("#rs-cam").setPointerCapture(e.pointerId);
});
$("#rs-cam").addEventListener("pointermove", (e) => {
  const a = rsArraste; if (!a) return;
  const x = Math.min(Math.max((e.clientX - a.dx - a.l) / Math.max(a.sw - a.cw, 1), 0), 1);
  const y = Math.min(Math.max((e.clientY - a.dy - a.t) / Math.max(a.sh - a.ch, 1), 0), 1);
  const C = cfgPosicao(P.react); C.x = x; C.y = y; renderStageReact();
});
$("#rs-cam").addEventListener("pointerup", () => {
  if (!rsArraste) return; rsArraste = null;
  const C = cfgPosicao(R_()), pos = { x: +C.x.toFixed(3), y: +C.y.toFixed(3) };
  tentar(() => salvarReact(R_().modo === "fundo_virtual" ? { recorte: pos } : { janela: pos }));
});

async function salvarReact(parcial) { await salvarProjeto({ react: parcial }); }

function renderReact() {
  if (!P) return;
  const R = R_(), x = P.react_extra || {};
  $("#rs-ativo").checked = R.ativo; $("#rs-ativo").disabled = !R.arquivo;
  $("#rs-remover").hidden = !R.arquivo;
  $$("[name=rs-modo]").forEach((r) => (r.checked = r.value === R.modo));
  $("#rs-janela-cfg").hidden = R.modo !== "janela";
  $("#rs-tam-cfg").hidden = R.modo === "dividido";
  const C = cfgPosicao(R);
  $("#rs-forma").value = R.janela.forma; $("#rs-w").value = Math.round(C.w * 100); $("#rs-w-v").textContent = Math.round(C.w * 100) + "%";
  for (const [id, k, mult] of [["#rs-ia-limiar", "limiar", 100], ["#rs-ia-borda", "borda", 100], ["#rs-ia-est", "estabilidade", 100]]) {
    $(id).value = Math.round(R.recorte_ia[k] * mult); $(id + "-v").textContent = Math.round(R.recorte_ia[k] * mult) + "%";
  }
  $("#rs-ia-aviso").textContent = x.matte_desatualizado ? "Você mudou os ajustes do recorte: clique em “Gerar recorte da gravação” de novo para aplicar."
    : x.matte_pronto ? "Recorte pronto: a prévia acima mostra a máscara real, quadro a quadro." : "";
  $("#rs-borda").checked = R.janela.borda; $("#rs-espelhar").checked = R.espelhar; $("#rs-desl").value = R.deslocamento;
  $("#rs-chroma").checked = R.chroma.ativo; $("#rs-chroma-cor").value = R.chroma.cor; $("#rs-despill").checked = R.chroma.despill;
  $("#rs-sim").value = Math.round(R.chroma.similaridade * 100); $("#rs-sim-v").textContent = Math.round(R.chroma.similaridade * 100) + "%";
  $("#rs-mist").value = Math.round(R.chroma.mistura * 100); $("#rs-mist-v").textContent = Math.round(R.chroma.mistura * 100) + "%";
  const dividido = R.modo === "dividido";
  $("#rs-chroma").disabled = $("#rs-ia").disabled = dividido;
  $("#rs-ia").checked = R.recorte_ia.ativo; $("#rs-ia").disabled = dividido || !x.matte_pronto;
  $("#rs-ia-gerar").disabled = !x.camera_ok || !x.recorte_ia?.ok;
  $("#rs-ia-gerar").title = x.recorte_ia?.ok ? "" : (x.recorte_ia?.motivo || "");
  const avisos = [];
  if (R.modo === "fundo_virtual" && !R.chroma.ativo && !R.recorte_ia.ativo) avisos.push("⚠ Fundo virtual precisa de chroma key ou recorte por IA ligado (senão aparece a câmera inteira).");
  if (P.tipo === "longo") avisos.push("Vídeo longo: use janela ou fundo virtual (a tela dividida é só para curtos).");
  $("#rs-status").innerHTML = (R.arquivo ? `Câmera: <b>${R.info ? R.info.dur.toFixed(1) + " s" : ""}</b> (${R.info?.w}×${R.info?.h})${x.camera_ok ? "" : " — <b>arquivo faltando</b>"}`
    : "Nenhuma câmera gravada ainda.") + (avisos.length ? "<br>" + avisos.join("<br>") : "");
  $("#rs-modos").querySelector('[value=dividido]').disabled = P.tipo === "longo";
  renderStageReact();
}
$("#rs-ativo").onchange = () => tentar(() => salvarReact({ ativo: $("#rs-ativo").checked }));
$$("[name=rs-modo]").forEach((r) => (r.onchange = () => tentar(() => salvarReact({ modo: r.value }))));
$("#rs-forma").onchange = () => tentar(() => salvarReact({ janela: { forma: $("#rs-forma").value } }));
$("#rs-w").oninput = () => { cfgPosicao(P.react).w = +$("#rs-w").value / 100; $("#rs-w-v").textContent = $("#rs-w").value + "%"; renderStageReact(); };
$("#rs-w").onchange = () => tentar(() => salvarReact({ [R_().modo === "fundo_virtual" ? "recorte" : "janela"]: { w: +$("#rs-w").value / 100 } }));
for (const [id, k] of [["#rs-ia-limiar", "limiar"], ["#rs-ia-borda", "borda"], ["#rs-ia-est", "estabilidade"]]) {
  $(id).oninput = () => { $(id + "-v").textContent = $(id).value + "%"; };
  $(id).onchange = () => tentar(() => salvarReact({ recorte_ia: { [k]: +$(id).value / 100 } }));
}
$("#rs-borda").onchange = () => tentar(() => salvarReact({ janela: { borda: $("#rs-borda").checked } }));
$("#rs-espelhar").onchange = () => tentar(() => salvarReact({ espelhar: $("#rs-espelhar").checked }));
$("#rs-desl").onchange = () => tentar(() => salvarReact({ deslocamento: +$("#rs-desl").value || 0 }));
$("#rs-chroma").onchange = () => tentar(() => salvarReact({ chroma: { ativo: $("#rs-chroma").checked } }));
$("#rs-chroma-cor").onchange = () => tentar(() => salvarReact({ chroma: { cor: $("#rs-chroma-cor").value } }));
$("#rs-despill").onchange = () => tentar(() => salvarReact({ chroma: { despill: $("#rs-despill").checked } }));
for (const [id, campo] of [["#rs-sim", "similaridade"], ["#rs-mist", "mistura"]]) {
  $(id).oninput = () => { P.react.chroma[campo] = +$(id).value / 100; $(id + "-v").textContent = $(id).value + "%"; comporReact(); };
  $(id).onchange = () => tentar(() => salvarReact({ chroma: { [campo]: +$(id).value / 100 } }));
}
$("#rs-ia").onchange = () => tentar(() => salvarReact({ recorte_ia: { ativo: $("#rs-ia").checked } }));
$("#rs-ia-gerar").onclick = () => tentar(async () => {
  await acompanhar(await api("POST", `${base()}/react/recorte`), "#tarefa-rs-ia");
  await recarregar(); aviso("Recorte gerado e ligado. Gere quadros (aba 7) para conferir as bordas.");
});
$("#rs-remover").onclick = () => tentar(async () => {
  if (!confirm("Tirar a câmera deste projeto? Os arquivos da gravação ficam na pasta react/ do projeto.")) return;
  await pararCamera(); P = await api("DELETE", `${base()}/react`); renderTudo();
});
$("#rs-proxy").onclick = () => tentar(async () => {
  await acompanhar(await api("POST", `${base()}/proxy`), "#tarefa-rs"); await recarregar(); aviso("Prévia pronta.");
});

// --- camera ao vivo e gravacao
async function listarDispositivos() {
  const devs = await navigator.mediaDevices.enumerateDevices();
  const opc = (tipo) => devs.filter((d) => d.kind === tipo).map((d) => `<option value="${d.deviceId}">${esc(d.label || tipo)}</option>`).join("");
  const cam = $("#rs-cam-sel").value, mic = $("#rs-mic-sel").value;
  $("#rs-cam-sel").innerHTML = opc("videoinput"); $("#rs-mic-sel").innerHTML = opc("audioinput");
  if (cam) $("#rs-cam-sel").value = cam; if (mic) $("#rs-mic-sel").value = mic;
}
async function ligarCamera() {
  await pararCamera();
  try {
    const cam = $("#rs-cam-sel").value, mic = $("#rs-mic-sel").value;
    rsStream = await navigator.mediaDevices.getUserMedia({
      video: { deviceId: cam ? { exact: cam } : undefined, width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
      audio: { deviceId: mic ? { exact: mic } : undefined, channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
  } catch (e) {
    const msg = e.name === "NotAllowedError" ? "permissão negada: libere câmera e microfone nesta página (ícone ao lado do endereço)"
      : e.name === "NotFoundError" ? "não encontrei câmera ou microfone" : e.name === "NotReadableError" ? "outro programa está usando a câmera" : e.message;
    throw new Error("Não consegui ligar a câmera: " + msg);
  }
  await listarDispositivos();
  const v = $("#rs-video"); v.srcObject = rsStream; v.loop = false; await v.play().catch(() => {});
  const inf = rsStream.getVideoTracks()[0].getSettings();
  if (inf.width) P.react.info = { dur: 0, w: inf.width, h: inf.height };
  const ctx = new AudioContext(); rsAnalisador = ctx.createAnalyser(); rsAnalisador.fftSize = 1024;
  ctx.createMediaStreamSource(rsStream).connect(rsAnalisador);
  const buf = new Float32Array(rsAnalisador.fftSize); rsStream.__ctx = ctx;
  (function medir() {
    if (!rsStream) return;
    rsAnalisador.getFloatTimeDomainData(buf);
    const db = 20 * Math.log10(buf.reduce((m, x) => Math.max(m, Math.abs(x)), 0) + 1e-9), n = $("#rs-nivel");
    n.style.width = Math.min(100, Math.max(0, (db + 60) / 60 * 100)) + "%"; n.style.background = db > -3 ? "var(--rosa)" : db > -12 ? "var(--acento)" : "var(--verde)";
    requestAnimationFrame(medir);
  })();
  $("#rs-gravar").disabled = false; $("#rs-estado").textContent = "câmera ligada";
  renderStageReact(); renderReact();
}
async function pararCamera() {
  if (rsRec && rsRec.state !== "inactive") rsRec.stop();
  if (rsStream) { rsStream.getTracks().forEach((t) => t.stop()); try { rsStream.__ctx?.close(); } catch { /* ok */ } rsStream = null; }
  const v = $("#rs-video"); v.srcObject = null; v.removeAttribute("src");
  ["#rs-gravar", "#rs-pausar", "#rs-parar"].forEach((s) => ($(s).disabled = true)); clearInterval(rsRelogio);
}
$("#rs-ligar").onclick = () => tentar(ligarCamera);
$("#rs-cam-sel").onchange = $("#rs-mic-sel").onchange = () => rsStream && tentar(ligarCamera);

function tempoGravado() { return rsAcum + (rsRec && rsRec.state === "recording" ? (performance.now() - rsT0) / 1000 : 0); }
$("#rs-gravar").onclick = () => tentar(async () => {
  if (!rsStream) throw new Error("ligue a câmera primeiro");
  const fundo = $("#rs-fundo"); fundo.pause(); fundo.currentTime = 0;
  for (const n of ["3", "2", "1"]) { $("#rs-relogio").textContent = n; await new Promise((r) => setTimeout(r, 700)); }
  rsPedacos = []; rsAcum = 0;
  const tipo = ["video/webm;codecs=vp8,opus", "video/webm"].find((t) => MediaRecorder.isTypeSupported(t)) || "";
  rsRec = new MediaRecorder(rsStream, { mimeType: tipo, videoBitsPerSecond: 4_000_000, audioBitsPerSecond: 192000 });
  rsRec.ondataavailable = (e) => e.data.size && rsPedacos.push(e.data);
  rsRec.onstart = () => { rsT0 = performance.now(); fundo.muted = false; if (P.tem_proxy) fundo.play().catch(() => {}); };   // jogo e camera comecam juntos
  rsRec.onstop = () => {
    rsAcum = tempoGravado(); rsBlob = new Blob(rsPedacos, { type: rsRec.mimeType || "video/webm" });
    $("#rs-rev").src = URL.createObjectURL(rsBlob); $("#rs-revisar").hidden = false;
    $("#rs-info").textContent = `${rsAcum.toFixed(1)} s gravados`; fundo.pause();
  };
  rsRec.start(250);
  $("#rs-gravar").disabled = true; $("#rs-pausar").disabled = $("#rs-parar").disabled = false;
  rsRelogio = setInterval(() => ($("#rs-relogio").textContent = mmss(tempoGravado())), 100);
  $("#rs-relogio").style.color = "var(--rosa)"; $("#rs-estado").textContent = "gravando";
});
$("#rs-pausar").onclick = () => {
  if (!rsRec) return;
  if (rsRec.state === "recording") { rsAcum = tempoGravado(); rsRec.pause(); $("#rs-fundo").pause(); $("#rs-pausar").textContent = "▶ Retomar"; $("#rs-estado").textContent = "pausado"; }
  else if (rsRec.state === "paused") { rsRec.resume(); rsT0 = performance.now(); $("#rs-fundo").play().catch(() => {}); $("#rs-pausar").textContent = "⏸ Pausar"; $("#rs-estado").textContent = "gravando"; }
};
$("#rs-parar").onclick = () => {
  if (!rsRec || rsRec.state === "inactive") return;
  rsRec.stop(); clearInterval(rsRelogio); $("#rs-relogio").style.color = "";
  $("#rs-pausar").disabled = $("#rs-parar").disabled = true; $("#rs-pausar").textContent = "⏸ Pausar"; $("#rs-gravar").disabled = false; $("#rs-estado").textContent = "gravação concluída";
};
async function enviarReact(blob, nome, usarAudio) {
  const fd = new FormData(); fd.append("arquivo", blob, nome);
  $("#tarefa-rs-up").textContent = "enviando e convertendo…";
  const r = await api("POST", `${base()}/react/gravacao?usar_audio=${usarAudio}`, fd);
  $("#tarefa-rs-up").textContent = "Concluído."; P = r; await pararCamera(); renderTudo();
  if (r.analise?.avisos?.length) aviso("Gravação salva, mas: " + r.analise.avisos.join(" "), true);
  else aviso("Câmera salva" + (r.analise ? " e microfone usado como narração (aba 5)" : "") + ". Próximo: 6 · Textos → Transcrever.");
}
$("#rs-salvar").onclick = () => tentar(async () => { if (!rsBlob) return; await enviarReact(rsBlob, "camera.webm", true); $("#rs-revisar").hidden = true; rsBlob = null; });
$("#rs-descartar").onclick = () => { rsBlob = null; $("#rs-revisar").hidden = true; };
$("#rs-enviar").onclick = () => tentar(async () => {
  const f = $("#rs-arquivo").files[0]; if (!f) throw new Error("escolha um vídeo"); await enviarReact(f, f.name, $("#rs-usar-audio").checked);
});
