// Clipador - aba 1 Fonte: videos-fonte, comparacao A x B e editor A x B.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// --------------------------------------------------------------------- 1 FONTE
function renderFontes() {
  $("#lista-fontes").innerHTML = P.fontes.map((f) => `
    <div class="cartao">
      <h3>${esc(f.nome)}</h3>
      <div class="dica">${f.info.w}×${f.info.h} · ${f.info.fps} fps · ${mmss(f.info.dur)} · ${f.info.audio ? "com áudio" : "sem áudio"} · ${f.cenas.length} cenas</div>
      <div class="linha">
        <label>Tarjas pretas removidas (crop w:h:x:y) <input data-crop="${f.id}" value="${esc(f.crop || "")}" placeholder="nenhuma"></label>
        <button data-salvar-crop="${f.id}">Salvar</button>
        <button data-remover="${f.id}">Remover</button>
      </div>
      <div class="dica">${esc(f.caminho)}</div>
    </div>`).join("") || `<p class="dica">Nenhum vídeo ainda.</p>`;
  renderComparacao();
}

// ---- comparacao A x B (tela dividida com dois videos, sem camera)
function renderComparacao() {
  const on = P.layout === "comparacao" && P.tipo !== "longo", C = P.comparacao || {};
  $("#card-comparacao").hidden = !on; if (!on) return;
  const opc = (sel) => `<option value="">— escolha —</option>` + P.fontes.map((f) => `<option value="${f.id}" ${f.id === sel ? "selected" : ""}>${esc(f.nome)}</option>`).join("");
  $("#cmp-a").innerHTML = opc(C.fonte_a); $("#cmp-b").innerHTML = opc(C.fonte_b);
  if (document.activeElement !== $("#cmp-rot-a")) $("#cmp-rot-a").value = C.rotulo_a || "";
  if (document.activeElement !== $("#cmp-rot-b")) $("#cmp-rot-b").value = C.rotulo_b || "";
  $("#cmp-audio").value = C.audio || "a"; $("#cmp-linha").checked = C.divisoria !== false;
  $("#cmp-tag-a").textContent = C.rotulo_a || "A"; $("#cmp-tag-b").textContent = C.rotulo_b || "B";
  $(".cmp-palco").classList.toggle("com-linha", C.divisoria !== false);
  const s = P.segmentos[segSel] || P.segmentos[0];     // mesmo recorte do render (foco de cada video)
  $("#cmp-va").style.objectPosition = `${(s?.foco_x ?? 0.5) * 100}% 50%`;
  $("#cmp-vb").style.objectPosition = `${(s?.foco_x_b ?? s?.foco_x ?? 0.5) * 100}% 50%`;
  const faltam = P.fontes.length < 2 ? "Adicione os 2 vídeos acima." : !(C.fonte_a && C.fonte_b) ? "Escolha o vídeo A e o B." :
    C.fonte_a === C.fonte_b ? "A e B são o mesmo vídeo (vale para comparar dois momentos dele)." : "";
  $("#cmp-info").textContent = faltam;
  $("#cmp-montar").disabled = $("#cmp-tocar").disabled = !(C.fonte_a && C.fonte_b);
  for (const [v, fid] of [["#cmp-va", C.fonte_a], ["#cmp-vb", C.fonte_b]]) {
    const url = fid ? `${base()}/fontes/${fid}/video` : "";
    const f = P.fontes.find((x) => x.id === fid), ch = f?.crop ? +f.crop.split(":")[1] : 0;
    $(v).style.transform = ch && ch < f.info.h ? `scale(${(f.info.h / ch).toFixed(3)})` : "";   // tira as tarjas, como o render
    if (($(v).dataset.src || "") !== url) { $(v).dataset.src = url; if (url) $(v).src = url; else $(v).removeAttribute("src"); }
  }
}
// ---- Editor A x B (aba Cortes): dois players, marcas de início/fim em cada um, sempre com a mesma duração
const CE = { fa: null, fb: null, a0: null, a1: null, b0: null, trecho: -1 };
const ceDur = () => (CE.a0 != null && CE.a1 != null ? +(CE.a1 - CE.a0).toFixed(3) : null);
const ceFonte = (id) => P.fontes.find((f) => f.id === id);
function ceCarregar(v, fid) {
  const url = fid ? `${base()}/fontes/${fid}/video` : "";
  if ((v.dataset.src || "") !== url) { v.dataset.src = url; if (url) v.src = url; else v.removeAttribute("src"); }
}
function renderCmpEditor() {
  const on = P.layout === "comparacao" && P.tipo !== "longo";
  $("#cmp-editor").hidden = !on; if (!on) return;
  const C = P.comparacao || {};
  // trecho clicado na lista: o editor abre com as marcas dele
  if (segSel !== CE.trecho) {
    CE.trecho = segSel;
    const s = P.segmentos[segSel];
    if (s) Object.assign(CE, { fa: s.fonte, fb: s.fonte_b || C.fonte_b || s.fonte, a0: s.ini, a1: s.fim, b0: s.ini_b ?? s.ini });
    else Object.assign(CE, { a0: null, a1: null, b0: null });
  }
  CE.fa = ceFonte(CE.fa) ? CE.fa : C.fonte_a || P.fontes[0]?.id || null;
  CE.fb = ceFonte(CE.fb) ? CE.fb : C.fonte_b || P.fontes[1]?.id || CE.fa;
  const opc = (sel) => P.fontes.map((f) => `<option value="${f.id}" ${f.id === sel ? "selected" : ""}>${esc(f.nome)}</option>`).join("") || `<option value="">adicione vídeos na aba 1</option>`;
  $("#ce-fonte-a").innerHTML = opc(CE.fa); $("#ce-fonte-b").innerHTML = opc(CE.fb);
  ceCarregar($("#ce-va"), CE.fa); ceCarregar($("#ce-vb"), CE.fb);
  ceInfo();
}
function ceInfo() {
  const d = ceDur(), fb = ceFonte(CE.fb), b1 = CE.b0 != null && d != null ? CE.b0 + d : null;
  $("#ce-info-a").textContent = `A: ${CE.a0 != null ? mmss(CE.a0) : "--"} → ${CE.a1 != null ? mmss(CE.a1) : "--"}`;
  $("#ce-info-b").textContent = `B: ${CE.b0 != null ? mmss(CE.b0) : "--"} → ${b1 != null ? mmss(b1) + " (mesmo tempo do A)" : "--"}`;
  $("#ce-dur").textContent = d != null ? `duração: ${d.toFixed(2)} s (A e B iguais)` : "duração: —";
  let aviso = "";
  if (CE.a0 == null || CE.a1 == null) aviso = "Marque o início e o fim no vídeo A.";
  else if (CE.b0 == null) aviso = "Agora ache a mesma cena no vídeo B e marque o início dele.";
  else if (fb && b1 > fb.info.dur + 0.05) aviso = `O vídeo B acaba em ${mmss(fb.info.dur)}: comece o B mais cedo ou encurte o A.`;
  $("#ce-aviso").textContent = aviso;
  const pronto = CE.a0 != null && CE.a1 != null && CE.b0 != null && !(fb && b1 > fb.info.dur + 0.05);
  $("#ce-adicionar").disabled = $("#ce-tocar").disabled = !pronto;
  const editando = CE.trecho >= 0 && P.segmentos[CE.trecho];
  $("#ce-salvar").hidden = $("#ce-novo").hidden = !editando;
  if (editando) { $("#ce-salvar").textContent = `Salvar no trecho ${CE.trecho + 1}`; $("#ce-salvar").disabled = !pronto; }
}
$("#ce-fonte-a").onchange = (e) => { CE.fa = e.target.value; CE.a0 = CE.a1 = null; ceCarregar($("#ce-va"), CE.fa); ceInfo(); };
$("#ce-fonte-b").onchange = (e) => { CE.fb = e.target.value; CE.b0 = null; ceCarregar($("#ce-vb"), CE.fb); ceInfo(); };
$("#cmp-editor").addEventListener("click", (e) => tentar(async () => {
  const acao = e.target.dataset.ce; if (!acao) return;
  const va = $("#ce-va"), vb = $("#ce-vb"), q = (f) => 1 / (ceFonte(f)?.info.fps || 30);
  const t = (v) => +v.currentTime.toFixed(3);
  if (acao === "a-volta" || acao === "a-avanca") { va.pause(); va.currentTime = Math.max(0, va.currentTime + (acao === "a-volta" ? -1 : 1) * q(CE.fa)); return; }
  if (acao === "b-volta" || acao === "b-avanca") { vb.pause(); vb.currentTime = Math.max(0, vb.currentTime + (acao === "b-volta" ? -1 : 1) * q(CE.fb)); return; }
  if (acao === "a-ini") { CE.a0 = t(va); if (CE.a1 != null && CE.a1 <= CE.a0 + 0.1) CE.a1 = null; }
  if (acao === "a-fim") { if (CE.a0 == null) throw new Error("marque primeiro o início do A"); if (t(va) <= CE.a0 + 0.1) throw new Error("o fim do A precisa ser depois do início"); CE.a1 = t(va); }
  if (acao === "b-ini") CE.b0 = t(vb);
  if (acao === "b-fim") {                      // fim do B define a duração: o fim do A acompanha
    if (CE.b0 == null || CE.a0 == null) throw new Error("marque antes o início do A e o início do B");
    const d = t(vb) - CE.b0; if (d <= 0.1) throw new Error("o fim do B precisa ser depois do início do B");
    const durA = ceFonte(CE.fa)?.info.dur ?? Infinity;
    if (CE.a0 + d > durA + 0.05) throw new Error(`com esse tempo o vídeo A passaria do fim (${mmss(durA)})`);
    CE.a1 = +(CE.a0 + d).toFixed(3);
  }
  ceInfo();
}));
// B acompanha o A: com os dois inícios marcados, mexer/tocar o A leva o B ao mesmo ponto da cena
(() => {
  const va = $("#ce-va"), vb = $("#ce-vb");
  const seguir = () => { if (!$("#ce-junto").checked || CE.a0 == null || CE.b0 == null || ceTocando) return; vb.currentTime = Math.max(0, CE.b0 + (va.currentTime - CE.a0)); };
  va.addEventListener("seeked", seguir);
  va.addEventListener("play", () => { if (!$("#ce-junto").checked || CE.a0 == null || CE.b0 == null) return; seguir(); vb.play().catch(() => {}); });
  va.addEventListener("pause", () => { if ($("#ce-junto").checked && CE.b0 != null) vb.pause(); });
})();
let ceTocando = false;
$("#ce-tocar").onclick = () => tentar(async () => {
  const va = $("#ce-va"), vb = $("#ce-vb"), C = P.comparacao || {}, d = ceDur();
  ceTocando = true; va.pause(); vb.pause();
  const pronto = (v, t) => new Promise((ok) => { v.addEventListener("seeked", ok, { once: true }); v.currentTime = t; setTimeout(ok, 1500); });
  await Promise.all([pronto(va, CE.a0), pronto(vb, CE.b0)]);       // os dois parados no ponto certo antes de tocar
  va.muted = C.audio === "b"; vb.muted = C.audio !== "b" && C.audio !== "ambos";
  await Promise.all([va.play(), vb.play()]).catch(() => {});
  const t0 = performance.now();
  const vigia = () => {
    if (va.currentTime >= CE.a0 + d || performance.now() - t0 > (d + 2) * 1000) { va.pause(); vb.pause(); va.muted = vb.muted = false; ceTocando = false; return; }
    const alvo = CE.b0 + (va.currentTime - CE.a0);                     // B segue o relógio do A (corrige atraso)
    if (Math.abs(vb.currentTime - alvo) > 0.12) vb.currentTime = alvo;
    requestAnimationFrame(vigia);
  };
  requestAnimationFrame(vigia);
});
const cePar = () => ({ fonte: CE.fa, ini: CE.a0, fim: CE.a1, fonte_b: CE.fb, ini_b: CE.b0 });
$("#ce-adicionar").onclick = () => tentar(async () => {
  const segs = [...P.segmentos, { foco_x: 0.5, zoom: 1, ...cePar() }];
  segSel = segs.length - 1;
  await salvarProjeto({ segmentos: segs });
  aviso(`Par adicionado como trecho ${segs.length} (Ctrl+Z desfaz). Marque o próximo ou confira com “▶ Prévia exata” na lista.`);
});
$("#ce-salvar").onclick = () => tentar(async () => {
  const segs = structuredClone(P.segmentos); Object.assign(segs[CE.trecho], cePar());
  await salvarProjeto({ segmentos: segs }); aviso(`Trecho ${CE.trecho + 1} atualizado (Ctrl+Z desfaz).`);
});
$("#ce-novo").onclick = () => { segSel = -1; CE.trecho = -2; renderSegmentos(); };
const salvarComparacao = (parcial) => tentar(() => salvarProjeto({ comparacao: parcial }));
$("#cmp-a").onchange = (e) => salvarComparacao({ fonte_a: e.target.value || null });
$("#cmp-b").onchange = (e) => salvarComparacao({ fonte_b: e.target.value || null });
$("#cmp-rot-a").onchange = (e) => salvarComparacao({ rotulo_a: e.target.value });
$("#cmp-rot-b").onchange = (e) => salvarComparacao({ rotulo_b: e.target.value });
$("#cmp-audio").onchange = (e) => salvarComparacao({ audio: e.target.value });
$("#cmp-linha").onchange = (e) => salvarComparacao({ divisoria: e.target.checked });
$("#cmp-trocar").onclick = () => { const C = P.comparacao; salvarComparacao({ fonte_a: C.fonte_b, fonte_b: C.fonte_a, rotulo_a: C.rotulo_b, rotulo_b: C.rotulo_a }); };
$("#cmp-montar").onclick = () => tentar(async () => {
  const antes = fotografia();
  P = await api("POST", `${base()}/comparacao/montar`, {});
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico(); renderTudo();
  aviso(`Comparação montada: ${P.segmentos.length} trecho(s) com A em cima e B embaixo. Confira com “▶ Ver lado a lado” ou gere quadros na aba 7.`,
    false, { rotulo: "Desfazer", fn: desfazer });
});
// prévia ao vivo: toca o trecho escolhido (ou o 1º) com A e B no mesmo instante; o som segue a opção "Som"
let cmpParar = null;
$("#cmp-tocar").onclick = () => tentar(async () => {
  if (cmpParar) { cmpParar(); return; }
  const C = P.comparacao, s = P.segmentos[segSel] || P.segmentos[0];
  const va = $("#cmp-va"), vb = $("#cmp-vb");
  const iniA = s ? s.ini : 0, iniB = s ? (s.ini_b ?? s.ini) : 0, dur = s ? s.fim - s.ini : 10;
  va.currentTime = iniA; vb.currentTime = iniB;
  va.muted = C.audio === "b"; vb.muted = C.audio === "a";
  await Promise.all([va.play(), vb.play()]);
  $("#cmp-tocar").textContent = "■ Parar";
  const t0 = performance.now();
  const vigia = () => { if (!cmpParar) return; if (va.currentTime >= iniA + dur || performance.now() - t0 > (dur + 1) * 1000) { cmpParar(); return; } requestAnimationFrame(vigia); };
  cmpParar = () => { va.pause(); vb.pause(); va.muted = vb.muted = true; cmpParar = null; $("#cmp-tocar").textContent = "▶ Ver lado a lado"; };
  requestAnimationFrame(vigia);
});
$("#lista-fontes").onclick = (e) => tentar(async () => {
  const id = e.target.dataset.salvarCrop || e.target.dataset.remover;
  if (!id) return;
  if (e.target.dataset.remover) { if (!confirm("Remover esta fonte do projeto? (o arquivo não é apagado)")) return; P = await api("DELETE", `${base()}/fontes/${id}`); renderTudo(); return; }
  const v = $(`[data-crop="${id}"]`).value.trim();
  if (v && !/^\d+:\d+:\d+:\d+$/.test(v)) throw new Error("formato do crop: largura:altura:x:y");
  await salvarProjeto({ fontes: P.fontes.map((f) => ({ id: f.id, crop: f.id === id ? v : f.crop })) });
  aviso("Recorte salvo.");
});
async function aposFonte(t) { await acompanhar(t, "#tarefa-fonte"); await recarregar(); aviso("Vídeo adicionado. Vá para 2 · Cortes."); }
$("#fonte-enviar").onclick = () => tentar(async () => {
  const f = $("#fonte-arquivo").files[0]; if (!f) throw new Error("escolha um arquivo");
  const fd = new FormData(); fd.append("arquivo", f);
  $("#tarefa-fonte").textContent = "enviando…";
  await aposFonte(await api("POST", `${base()}/fontes/upload`, fd));
});
$("#fonte-usar-caminho").onclick = () => tentar(async () => aposFonte(await api("POST", `${base()}/fontes/caminho`, { caminho: $("#fonte-caminho").value })));
$("#fonte-baixar").onclick = () => tentar(async () => aposFonte(await api("POST", `${base()}/fontes/url`, { url: $("#fonte-url").value })));
