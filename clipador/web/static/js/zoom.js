// Clipador - zoom por trecho (preset + ajustes).
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ---- zoom por trecho (core/zoom.py): preset + ajustes; "personalizado" quando o usuario mexe num ajuste
let ZOOM = null;
api("GET", "/api/zoom/presets").then((z) => (ZOOM = z)).catch(() => {});
function linhaZoom(s, i) {
  if (P.layout === "comparacao" && P.tipo !== "longo") return "";
  const fx = s.zoom_fx, presets = ZOOM ? ZOOM.presets : {};
  const opc = [["nenhum", "sem zoom"], ...Object.entries(presets).map(([k, p]) => [k, p.nome]), ...(fx?.preset === "personalizado" ? [["personalizado", "personalizado"]] : [])]
    .map(([k, n]) => `<option value="${k}" ${(fx ? fx.preset : "nenhum") === k ? "selected" : ""}>${esc(n)}</option>`).join("");
  const legado = !fx && (s.zoom ?? 1) > 1.001 ? ` <span class="dica">(zoom antigo ${s.zoom}× — escolha um preset para trocar)</span>` : "";
  if (!fx) return `<div class="linha zoom-linha"><label>Zoom <select data-zfx="preset">${opc}</select></label>${legado}</div>`;
  const dica = presets[fx.preset]?.dica || "";
  return `<div class="linha zoom-linha"><label>Zoom <select data-zfx="preset">${opc}</select></label><span class="dica">${esc(dica)}</span></div>
    <div class="linha zoom-linha">
      <label>força <input type="range" min="1.05" max="2" step="0.05" data-zfx="intensidade" value="${fx.intensidade}"> <b>${(+fx.intensidade).toFixed(2)}×</b></label>
      <label>começa em <input type="number" min="0" step="0.1" data-zfx="inicio" value="${fx.inicio}"> s</label>
      <label>leva <input type="number" min="0" step="0.05" data-zfx="duracao" value="${fx.duracao}"> s <span class="dica">${fx.duracao ? "" : "(o trecho todo)"}</span></label>
      <label>curva <select data-zfx="curva">${["suave", "rapida", "linear"].map((c) => `<option ${fx.curva === c ? "selected" : ""} value="${c}">${{ suave: "suave", rapida: "rápida", linear: "constante" }[c]}</option>`).join("")}</select></label>
      <label><input type="checkbox" data-zfx="volta" ${fx.volta ? "checked" : ""}> volta ao normal</label>
    </div>
    <div class="linha zoom-linha">
      <label title="Ponto que fica parado na tela enquanto o zoom acontece">ponto ← → <input type="range" min="0" max="1" step="0.01" data-zfx="foco_x" value="${fx.foco_x}"> <b>${Math.round(fx.foco_x * 100)}%</b></label>
      <label>ponto ↑ ↓ <input type="range" min="0" max="1" step="0.01" data-zfx="foco_y" value="${fx.foco_y}"> <b>${Math.round(fx.foco_y * 100)}%</b></label>
      <button class="mini" data-acao="previa-trecho" aria-label="Prévia do trecho ${i + 1} com o zoom">▶ Prévia exata</button>
      <button class="mini" data-acao="zoom-preset" title="Guarda força, tempo, curva e volta deste zoom como um preset seu (Biblioteca de estilos)" aria-label="Salvar o zoom do trecho ${i + 1} como preset">Salvar como preset</button>
    </div>`;
}
$("#lista-segmentos").addEventListener("change", (e) => tentar(async () => {
  const z = e.target.dataset.zfx; if (!z) return;
  const i = +e.target.closest("li").dataset.i, segs = structuredClone(P.segmentos), s = segs[i];
  if (z === "preset") {
    const v = e.target.value;
    if (v === "nenhum") { delete s.zoom_fx; s.zoom = 1; }
    else if (v !== "personalizado") { const pr = ZOOM.presets[v]; s.zoom_fx = { preset: v, intensidade: pr.intensidade, inicio: s.zoom_fx?.inicio ?? pr.inicio, duracao: pr.duracao, curva: pr.curva, volta: pr.volta, segura: pr.segura, foco_x: s.zoom_fx?.foco_x ?? 0.5, foco_y: s.zoom_fx?.foco_y ?? 0.5 }; s.zoom = 1; }
  } else {
    s.zoom_fx[z] = e.target.type === "checkbox" ? e.target.checked : +e.target.value;
    if (["intensidade", "inicio", "duracao", "curva", "volta"].includes(z)) s.zoom_fx.preset = "personalizado";
    if (z === "curva") s.zoom_fx.curva = e.target.value;
  }
  segSel = i; await salvarProjeto({ segmentos: segs });
}));
$("#lista-segmentos").addEventListener("change", (e) => tentar(async () => {
  const k = e.target.dataset.k; if (!k) return;
  const i = +e.target.closest("li").dataset.i, segs = structuredClone(P.segmentos);
  const num = ["ini", "fim", "foco_x", "zoom", "ini_b", "foco_x_b"].includes(k);
  segs[i][k] = num ? +e.target.value : e.target.value;
  if (segs[i].fim <= segs[i].ini) throw new Error("o fim precisa ser depois do início");
  await salvarProjeto({ segmentos: segs });
}));

// moldura amarela mostrando o que entra no vídeo vertical (layouts tela cheia / empilhado)
function desenharMoldura() {
  if (!P) return;                              // evento do player antes de abrir um projeto
  const m = $("#moldura-crop"), v = $("#player-fonte"), s = P.segmentos[segSel];
  const f = s && P.fontes.find((x) => x.id === s.fonte);
  if (!s || !f || P.tipo === "longo" || P.layout === "comparacao" || !v.videoWidth || $("#cortes-fonte").value !== s.fonte) { m.style.display = "none"; return; }
  const [cw, ch, cx, cy] = f.crop ? f.crop.split(":").map(Number) : [f.info.w, f.info.h, 0, 0];
  const asp = P.layout === "tela_cheia" ? 9 / 16 : 1080 / 864;
  let rw = ch * asp, rh = ch; if (rw > cw) { rw = cw; rh = cw / asp; }
  const rx = cx + (s.foco_x ?? 0.5) * (cw - rw), ry = cy + (ch - rh) / 2;
  const esc_ = Math.min(v.clientWidth / v.videoWidth, v.clientHeight / v.videoHeight);
  const ox = (v.clientWidth - v.videoWidth * esc_) / 2, oy = (v.clientHeight - v.videoHeight * esc_) / 2;
  Object.assign(m.style, { display: "block", left: ox + rx * esc_ + "px", top: oy + ry * esc_ + "px", width: rw * esc_ + "px", height: rh * esc_ + "px" });
  const mz = $("#moldura-zoom"), fx = s.zoom_fx;
  mz.hidden = !fx;
  if (fx) {                      // janela do zoom no auge: W/z x H/z com o ponto escolhido parado
    const z = fx.intensidade, w = rw * esc_ / z, h = rh * esc_ / z;
    Object.assign(mz.style, { left: fx.foco_x * (rw * esc_ - w) - 2 + "px", top: fx.foco_y * (rh * esc_ - h) - 2 + "px", width: w + "px", height: h + "px" });
  }
}
$("#player-fonte").addEventListener("loadedmetadata", desenharMoldura);
window.addEventListener("resize", desenharMoldura);
