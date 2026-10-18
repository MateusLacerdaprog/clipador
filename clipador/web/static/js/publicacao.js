// Clipador - publicacao por rede (YouTube, TikTok, Instagram): campos, verificacao, capa e PUBLICACAO.md.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// --- publicacao (aba 7): cada campo salva na hora; limites e verificacao ficam no servidor (core/publicacao.py)
let pubRede = "youtube";
const PUB_CAMPOS = {        // id do campo -> caminho em P.publicacao (+ como transformar o texto)
  "pub-chave": "palavra_chave", "pub-titulo": "titulo", "pub-descricao": "descricao", "pub-hashtags": "hashtags#",
  "pub-tags": "youtube.tags,", "pub-categoria": "youtube.categoria", "pub-privacidade": "youtube.privacidade",
  "pub-tk-legenda": "tiktok.legenda", "pub-tk-hashtags": "tiktok.hashtags#",
  "pub-ig-legenda": "instagram.legenda", "pub-ig-hashtags": "instagram.hashtags#",
  "pub-credito": "credito", "pub-ponte": "ponte",
};
const PUB_DECL = { "pub-criancas": "feito_para_criancas", "pub-alterado": "conteudo_alterado" };

function pubLer(caminho) {
  const [k, sub] = caminho.replace(/[#,]$/, "").split(".");
  const v = sub ? (P.publicacao?.[k] || {})[sub] : P.publicacao?.[k];
  if (caminho.endsWith("#")) return (v || []).join(" ");
  if (caminho.endsWith(",")) return (v || []).join(", ");
  return v ?? "";
}

function pubParcial(caminho, valor) {
  const [k, sub] = caminho.replace(/[#,]$/, "").split(".");
  return sub ? { [k]: { [sub]: valor } } : { [k]: valor };
}

function pubContadores() {
  const t = $("#pub-titulo").value.length;
  $("#pub-titulo-n").textContent = `${t}/100${t > 70 ? " · acima de 70 corta no celular" : ""}`;
  $("#pub-tk-n").textContent = `${$("#pub-tk-legenda").value.length}/4000`;
  $("#pub-ig-n").textContent = `${$("#pub-ig-legenda").value.length}/2200`;
}

function renderPublicacao() {
  if (!P) return;
  for (const [id, caminho] of Object.entries(PUB_CAMPOS)) {
    const el = $("#" + id);
    if (el && document.activeElement !== el) el.value = pubLer(caminho);   // nao apaga o que esta sendo digitado
  }
  for (const [nome, campo] of Object.entries(PUB_DECL)) {
    const v = P.publicacao?.youtube?.[campo];
    $$(`input[name="${nome}"]`).forEach((r) => { r.checked = (v === true && r.value === "sim") || (v === false && r.value === "nao"); });
  }
  const capa = P.publicacao?.capa || {};
  if (document.activeElement !== $("#pub-capa-tempo")) $("#pub-capa-tempo").value = capa.tempo ?? "";
  const img = $("#pub-capa-img");
  img.hidden = !capa.arquivo;
  if (capa.arquivo) img.src = `${base()}/arquivo?caminho=${encodeURIComponent(capa.arquivo)}&v=${encodeURIComponent(capa.tempo)}`;
  pubContadores();
}

for (const [id, caminho] of Object.entries(PUB_CAMPOS)) {
  $("#" + id).addEventListener("change", (e) => tentar(async () => {
    let v = e.target.value;
    if (caminho.endsWith(",")) v = v.split(",").map((s) => s.trim()).filter(Boolean);
    else if (caminho.endsWith("#")) v = v.split(/\s+/).filter(Boolean);
    await salvarProjeto({ publicacao: pubParcial(caminho, v) });
  }));
}
for (const [nome, campo] of Object.entries(PUB_DECL)) {
  $$(`input[name="${nome}"]`).forEach((r) => r.addEventListener("change", () => tentar(() =>
    salvarProjeto({ publicacao: { youtube: { [campo]: r.value === "sim" } } }))));
}
["#pub-titulo", "#pub-tk-legenda", "#pub-ig-legenda"].forEach((s) => $(s).addEventListener("input", pubContadores));

$$("[data-rede]").forEach((b) => b.addEventListener("click", () => {
  pubRede = b.dataset.rede;
  $$("[data-rede]").forEach((x) => { const on = x === b; x.classList.toggle("ativo", on); x.setAttribute("aria-pressed", String(on)); });
  $$("[data-pub]").forEach((d) => { d.hidden = d.dataset.pub !== pubRede; });
}));

$("#pub-adaptar").onclick = () => tentar(async () => {
  const s = await api("GET", `${base()}/publicacao/adaptar`);
  await salvarProjeto({ publicacao: s });
  aviso("TikTok e Instagram preenchidos a partir do YouTube. Ajuste o tom de cada rede.", false, { rotulo: "Desfazer", fn: desfazer });
});

async function pubVerificar() {
  const r = await api("GET", `${base()}/publicacao/verificar`);
  renderItens(r.itens, $("#pub-verif"));
  const m = r.mencoes, s = (v) => (v === null ? "?" : v ? "✓" : "✗");
  $("#pub-mencoes").textContent = m.chave
    ? `“${m.chave}” — falada ${s(m.falada)} · na tela ${s(m.na_tela)} · YouTube ${s(m.post.youtube)} · TikTok ${s(m.post.tiktok)} · Instagram ${s(m.post.instagram)}`
    : "";
}
$("#pub-verificar").onclick = () => tentar(pubVerificar);

$("#pub-copiar").onclick = () => tentar(async () => {
  const pub = P.publicacao, tags = (l) => (l?.length ? "\n\n" + l.join(" ") : "");
  let txt;
  if (pubRede === "youtube") {
    const caps = P.formato_cfg?.capitulos && $("#txt-capitulos").value ? "\n\n" + $("#txt-capitulos").value : "";
    txt = `${pub.titulo}\n\n${pub.descricao}${caps}${tags(pub.hashtags)}`;
  } else txt = `${pub[pubRede].legenda}${tags(pub[pubRede].hashtags)}`;
  await navigator.clipboard.writeText(txt.trim());
  aviso(`Texto do ${{ youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram" }[pubRede]} copiado.`);
});

$("#pub-exportar").onclick = () => tentar(async () => {
  const r = await api("POST", `${base()}/publicacao/exportar`);
  const a = $("#pub-md");
  a.href = `${base()}/arquivo?caminho=${encodeURIComponent(r.arquivo)}&v=${Date.now()}`; a.hidden = false;
  aviso(`${r.arquivo} salvo na pasta do projeto.`);
  await pubVerificar();
});

$("#pub-capa").onclick = () => tentar(async () => {
  const t = parseFloat($("#pub-capa-tempo").value);
  if (!Number.isFinite(t) || t < 0) throw new Error("Digite o instante da capa em segundos (ex.: 1.5).");
  P = await api("POST", `${base()}/publicacao/capa`, { tempo: t });
  renderTudo();
  aviso("Capa gerada (capa.png na pasta do projeto).");
});
