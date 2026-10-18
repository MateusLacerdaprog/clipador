// Clipador - provedores de IA, referencias e assistente.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

// ------------------------------------------------------------- IA e referencias
$$("[data-fechar]").forEach((b) => (b.onclick = () => b.closest("dialog").close()));
let IA = null, PERFIS = [];
const usd = (v) => (v == null ? "—" : `US$ ${(+v).toFixed(4)}`);

async function carregarIA() { IA = await api("GET", "/api/ia"); return IA; }
async function carregarPerfis() { PERFIS = (await api("GET", "/api/referencias")).perfis; return PERFIS; }

// --- dialogo Provedores de IA
$("#abrir-ia").onclick = () => tentar(async () => { await carregarIA(); renderIA(); $("#dlg-ia").showModal(); });
function renderIA() {
  $("#lista-provedores").innerHTML = IA.provedores.map((p) => `
    <div class="cartao prov ${IA.provedor_ativo === p.id ? "ativo" : ""}" data-prov="${p.id}">
      <div class="linha"><b class="cresce">${esc(p.nome)}</b>
        <label><input type="radio" name="prov-ativo" value="${p.id}" ${IA.provedor_ativo === p.id ? "checked" : ""}> usar este</label></div>
      ${p.precisa_chave ? `<div class="linha">
          ${p.credencial ? `<span class="selo ok">chave ${esc(p.mascara)} · ${esc(p.origem)}</span>
            ${p.origem === "cofre do Windows" ? `<button class="mini" data-acao="remover">Remover chave</button>` : ""}`
          : `<span class="selo pend">sem chave</span>`}
          <a href="${p.painel}" target="_blank" rel="noopener" class="dica">criar chave no painel ↗</a></div>
        <div class="linha"><input type="password" class="cresce" data-campo="chave" autocomplete="off" aria-label="Chave da API de ${esc(p.nome)}" placeholder="cole a chave da API aqui">
          <button data-acao="salvar-chave">Salvar no cofre</button></div>`
        : `<div class="linha dica">Roda no seu PC, sem chave e sem custo por uso. Precisa do Ollama instalado e de um modelo baixado.</div>`}
      <div class="linha"><label>Modelo <input list="modelos-${p.id}" data-campo="modelo" value="${esc(p.modelo)}" placeholder="clique em Testar para listar"></label>
        <datalist id="modelos-${p.id}"></datalist>
        <button data-acao="testar">Testar conexão</button><span class="dica" data-campo="teste"></span></div>
      <div class="linha"><label><input type="checkbox" data-campo="consentimento" ${p.consentimento ? "checked" : ""}>
        Aceito enviar o <b>texto</b> do projeto (roteiro, legenda, rótulos, formato) para ${esc(p.nome)}${p.precisa_chave ? " — sujeito aos termos e à cobrança do provedor" : ""}.</label></div>
      ${p.id === "claude" ? `<p class="dica">Padrão: claude-opus-5-5 (US$ 4 / 20 por milhão de tokens de entrada/saída). Recusas por engano são refeitas automaticamente por outro modelo no servidor (fallback).</p>` : ""}
    </div>`).join("");
  const L = IA.limites, H = IA.historico;
  $("#lim-dia").value = L.chamadas_por_dia; $("#lim-tokens").value = L.max_tokens_saida; $("#lim-orc").value = L.orcamento_mensal_usd;
  $("#hist-ativo").checked = H.ativo; $("#hist-conteudo").checked = H.guardar_conteudo;
  $("#uso-ia").textContent = `Hoje: ${IA.uso.chamadas_hoje} chamada(s) · mês: ${IA.uso.chamadas_mes} · custo conhecido no mês: ${usd(IA.uso.custo_mes_usd)}`;
}
$("#lista-provedores").addEventListener("click", (e) => tentar(async () => {
  const card = e.target.closest("[data-prov]"); if (!card) return;
  const pid = card.dataset.prov, acao = e.target.dataset.acao;
  if (acao === "salvar-chave") {
    const inp = card.querySelector('[data-campo="chave"]'); const chave = inp.value.trim(); inp.value = "";
    if (!chave) throw new Error("cole a chave antes de salvar");
    IA = await api("POST", "/api/ia/credencial", { provedor: pid, chave }); renderIA(); aviso("Chave guardada no cofre do Windows.");
  } else if (acao === "remover") {
    if (!confirm("Remover a chave deste provedor do cofre do Windows?")) return;
    IA = await api("DELETE", `/api/ia/credencial/${pid}`); renderIA();
  } else if (acao === "testar") {
    const out = card.querySelector('[data-campo="teste"]'); out.textContent = "testando…";
    const r = await api("POST", "/api/ia/testar", { provedor: pid });
    if (!r.ok) { out.textContent = "✗ " + r.erro; return; }
    $(`#modelos-${pid}`).innerHTML = r.modelos.map((m) => `<option value="${esc(m)}">`).join("");
    out.textContent = `✓ conectado · ${r.modelos.length} modelos disponíveis`;
  }
}));
$("#lista-provedores").addEventListener("change", (e) => tentar(async () => {
  const card = e.target.closest("[data-prov]"); if (!card) return;
  const pid = card.dataset.prov, campo = e.target.dataset.campo;
  if (e.target.name === "prov-ativo") IA = await api("PUT", "/api/ia/config", { provedor_ativo: pid });
  else if (campo === "modelo") IA = await api("PUT", "/api/ia/config", { provedores: { [pid]: { modelo: e.target.value.trim() } } });
  else if (campo === "consentimento") IA = await api("PUT", "/api/ia/config", { provedores: { [pid]: { consentimento: e.target.checked } } });
  else return;
  renderIA(); renderStatusIA();
}));
$("#salvar-limites").onclick = () => tentar(async () => {
  IA = await api("PUT", "/api/ia/config", {
    limites: { chamadas_por_dia: +$("#lim-dia").value, max_tokens_saida: +$("#lim-tokens").value, orcamento_mensal_usd: +$("#lim-orc").value },
    historico: { ativo: $("#hist-ativo").checked, guardar_conteudo: $("#hist-conteudo").checked } });
  renderIA(); aviso("Configurações de IA salvas.");
});
$("#apagar-hist").onclick = () => tentar(async () => {
  if (!confirm("Apagar todo o histórico de tarefas de IA?")) return;
  await api("DELETE", "/api/ia/historico"); await carregarIA(); renderIA(); $("#hist-ia").innerHTML = ""; aviso("Histórico apagado.");
});
$("#dlg-ia details").addEventListener("toggle", (e) => e.target.open && tentar(async () => {
  const h = await api("GET", "/api/ia/historico");
  $("#hist-ia").innerHTML = h.map((r) => `<div>${esc(r.data)} · ${esc(r.provedor)} ${esc(r.modelo || "")} · ${esc(r.tarefa)} · ${r.ok ? "ok" : "erro: " + esc(r.erro)}
    ${r.tokens_entrada != null ? `· ${r.tokens_entrada}+${r.tokens_saida} tokens · ${usd(r.custo_usd)}` : ""}</div>`).join("") || "vazio";
}));

// --- dialogo Referencias
$("#abrir-ref").onclick = () => tentar(async () => { await renderPerfis(); $("#dlg-ref").showModal(); });
async function renderPerfis() {
  const r = await api("GET", "/api/referencias"); PERFIS = r.perfis;
  $("#ref-aspectos").innerHTML = Object.entries(r.aspectos).filter(([k]) => k !== "visual")
    .map(([k, v]) => `<label title="${esc(v)}"><input type="checkbox" value="${k}" checked> ${esc(v.split(" (")[0])}</label>`).join("");
  const det = await Promise.all(PERFIS.map((p) => api("GET", `/api/referencias/${p.id}`)));
  $("#lista-perfis").innerHTML = det.map((p) => {
    const o = p.observado, c = o.curtos || {}, l = o.longos || {}, f = o.fala || {}, v = o.visual || {};
    return `<div class="cartao"><div class="linha"><b class="cresce">${esc(p.nome)}</b><span class="dica">coletado em ${esc(p.fonte.data)} ·
      ${p.fonte.amostra.curtos} curtos, ${p.fonte.amostra.longos} longos</span><button class="mini" data-apagar-perfil="${p.id}">Apagar</button></div>
      <ul class="resumo-audio">
        ${c.dur_mediana_s ? `<li>Shorts: ${c.dur_p25_s}–${c.dur_p75_s} s (mediana ${c.dur_mediana_s} s, medidos ${c.com_duracao ?? c.n})</li>` : ""}
        ${l.dur_mediana_s ? `<li>Longos: mediana ${Math.round(l.dur_mediana_s / 60)} min</li>` : ""}
        ${f.ppm_curtos_mediana ? `<li>Fala nos Shorts: ${f.ppm_curtos_mediana} palavras/min · ${f.palavras_3s_curtos_mediana} palavras nos 3 primeiros segundos</li>` : ""}
        ${v.cortes_por_min_curtos ? `<li>Cortes nos Shorts: ~${v.cortes_por_min_curtos}/min (cena de ~${(60 / v.cortes_por_min_curtos).toFixed(1)} s) · ${esc(v.metodo || "")}</li>` : `<li class="dica">Ritmo de cortes: não medido</li>`}
        ${(v.notas || []).map((n) => `<li class="dica">${esc(n)}</li>`).join("")}
        ${o.publicacao?.dias_entre_posts_mediana != null ? `<li>Publica a cada ~${o.publicacao.dias_entre_posts_mediana} dia(s)</li>` : ""}
      </ul>
      <details><summary class="dica">limitações</summary><ul>${p.limitacoes.map((x) => `<li class="dica">${esc(x)}</li>`).join("")}</ul></details></div>`;
  }).join("") || `<p class="dica">Nenhum perfil ainda.</p>`;
}
$("#lista-perfis").addEventListener("click", (e) => tentar(async () => {
  const id = e.target.dataset.apagarPerfil; if (!id) return;
  if (!confirm("Apagar este perfil de referência?")) return;
  await api("DELETE", `/api/referencias/${id}`); await renderPerfis();
}));
$("#ref-gerar").onclick = () => tentar(async () => {
  const canais = $("#ref-canais").value.split(/\s+/).filter(Boolean);
  const aspectos = $$("#ref-aspectos input:checked").map((i) => i.value);
  const t = await api("POST", "/api/referencias", { nome: $("#ref-nome").value, canais, aspectos });
  await acompanhar(t, "#tarefa-ref"); await renderPerfis(); aviso("Perfil gerado.");
});

// --- aba 8 Assistente
async function abrirAssistente() {
  await Promise.all([carregarIA(), carregarPerfis()]);
  $("#ia-tarefa").innerHTML = Object.entries(IA.tarefas).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  const opts = `<option value="">nenhuma</option>` + PERFIS.map((p) => `<option value="${p.id}">${esc(p.nome)}</option>`).join("");
  $("#ia-perfil").innerHTML = opts; $("#ref-sel").innerHTML = opts.replace("nenhuma", "escolha um perfil");
  if (P.referencia) { $("#ia-perfil").value = P.referencia; $("#ref-sel").value = P.referencia; }
  renderStatusIA(); compararRef(); renderAnteriores();
}
function renderStatusIA() {
  if (!IA || !$("#ia-status")) return;
  const p = IA.provedores.find((x) => x.id === IA.provedor_ativo);
  $("#ia-status").innerHTML = !p ? `Nenhum provedor ativo. <a href="#" id="link-ia">Configurar provedores de IA</a> (a edição manual funciona sem IA).`
    : `Usando <b>${esc(p.nome)}</b> ${esc(p.modelo || "(sem modelo)")}${!p.credencial ? " — <b>falta a chave</b>" : ""}${!p.consentimento ? " — <b>falta o consentimento</b>" : ""} · hoje ${IA.uso.chamadas_hoje}/${IA.limites.chamadas_por_dia}`;
  const l = $("#link-ia"); if (l) l.onclick = (e) => { e.preventDefault(); $("#abrir-ia").click(); };
}
const pedidoIA = () => ({ extra: $("#ia-extra").value, perfil: $("#ia-perfil").value || null });
$("#ia-ver").onclick = () => tentar(async () => {
  const r = await api("POST", `${base()}/ia/previa/${$("#ia-tarefa").value}`, pedidoIA());
  const el = $("#ia-previa"); el.hidden = false;
  el.textContent = `Para: ${r.provedor || "(nenhum provedor ativo)"} · ${r.caracteres} caracteres · vídeo/áudio: não enviados\n\n[INSTRUÇÕES]\n${r.sistema}\n\n[CONTEÚDO]\n${r.prompt}`;
});
$("#ia-pedir").onclick = () => tentar(async () => {
  const r = await acompanhar(await api("POST", `${base()}/ia/${$("#ia-tarefa").value}`, pedidoIA()), "#tarefa-ia");
  renderResultado(r); renderAnteriores(); await carregarIA(); renderStatusIA();
});
function renderResultado(r) {
  const d = r.dados || {}, botao = (acao, valor, rot) => `<button class="mini" data-aplicar="${acao}" data-valor="${esc(valor)}">${rot}</button>`;
  let h = `<div class="cartao resultado-ia"><div class="linha"><span class="selo pend">${esc(r.origem)}</span>
    <span class="dica">${esc(r.data)} · ${r.tokens.entrada}+${r.tokens.saida} tokens · ${usd(r.custo_usd)}</span></div>`;
  if (r.tarefa === "titulos") {
    h += `<h4>Títulos</h4>` + (d.titulos || []).map((t) => `<div class="linha"><span class="cresce">${esc(t.texto)} <span class="dica">— ${esc(t.porque)}</span></span>${botao("titulo", t.texto, "Usar")}</div>`).join("");
    h += `<h4>Ganchos para a tela</h4>` + (d.ganchos || []).map((t) => `<div class="linha"><span class="cresce">${esc(t.texto)} <span class="dica">— ${esc(t.porque)}</span></span>${botao("gancho", t.texto, "Usar como gancho")}</div>`).join("");
    h += `<h4>Descrição</h4><p style="white-space:pre-wrap">${esc(d.descricao)}</p>${botao("descricao", d.descricao || "", "Usar descrição")}`;
    h += `<h4>Hashtags</h4><p>${esc((d.hashtags || []).join(" "))}</p>${botao("hashtags", (d.hashtags || []).join(" "), "Usar hashtags")}`;
  } else if (r.tarefa === "roteiro") {
    h += `<h4>Gancho</h4><p>${esc(d.gancho)}</p>${botao("gancho", d.gancho || "", "Usar como gancho")}
      <h4>Roteiro${d.duracao_estimada_s ? ` (~${Math.round(d.duracao_estimada_s)} s)` : ""}</h4><pre class="previa-envio">${esc(d.roteiro)}</pre>${botao("roteiro", d.roteiro || "", "Substituir o roteiro")}
      ${(d.a_confirmar || []).length ? `<h4>⚠ Confirmar antes de gravar</h4><ul>${d.a_confirmar.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      ${(d.notas || []).length ? `<h4>Notas</h4><ul>${d.notas.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}`;
  } else {
    h += `<p>${esc(d.resumo)}</p><p>Nota do gancho: <b>${d.nota_gancho ?? "—"}/10</b></p>
      <h4>Pontos fortes</h4><ul>${(d.pontos_fortes || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <h4>Problemas</h4><ul>${(d.problemas || []).map((x) => `<li><b>[${esc(x.prioridade)}]</b> ${esc(x.item)} → ${esc(x.sugestao)}</li>`).join("")}</ul>`;
  }
  $("#ia-resultado").innerHTML = h + `<p class="dica">Sugestões da IA são editáveis e só mudam o projeto quando você clica em "Usar". Confira fatos antes de publicar.</p></div>`;
}
$("#ia-resultado").addEventListener("click", (e) => tentar(async () => {
  const acao = e.target.dataset.aplicar; if (!acao) return;
  const v = e.target.dataset.valor;
  if (acao === "gancho") await salvarProjeto({ gancho: { texto: v.slice(0, 80), ate: P.gancho.ate || 3 } });
  else if (acao === "roteiro") { if (!confirm("Substituir o roteiro atual?")) return; await salvarProjeto({ roteiro: v }); }
  else await salvarProjeto({ publicacao: { [acao]: acao === "hashtags" ? v.split(/\s+/) : v } });
  aviso("Aplicado. Desfaça com Ctrl+Z se não gostar.");
}));
async function renderAnteriores() {
  const s = await api("GET", `${base()}/ia/sugestoes`);
  $("#ia-anteriores").innerHTML = s.map((r, i) => `<div><a href="#" data-sug="${i}">${esc(r.data)} · ${esc(IA?.tarefas?.[r.tarefa] || r.tarefa)}</a></div>`).join("") || "nenhuma ainda";
  $("#ia-anteriores").onclick = (e) => { const i = e.target.dataset.sug; if (i != null) { e.preventDefault(); renderResultado(s[+i]); } };
}
async function compararRef() {
  const id = $("#ref-sel").value;
  if (!id) { $("#ref-comparacao").innerHTML = PERFIS.length ? "" : `<p class="dica">Nenhum perfil. Abra 📚 Referências na barra lateral.</p>`; return; }
  const c = await api("GET", `${base()}/referencia/${id}`);
  $("#ref-comparacao").innerHTML = `<table class="tabela"><thead><tr><th>Aspecto</th><th>Referência</th><th>Seu projeto</th><th></th></tr></thead><tbody>` +
    c.itens.map((i) => `<tr><td>${esc(i.aspecto)}</td><td>${esc(i.referencia)}</td><td>${esc(i.seu_projeto)}</td>
      <td>${i.situacao === "ok" ? `<span class="selo ok">ok</span>` : `<span class="selo pend" title="${esc(i.sugestao)}">ajustar</span><div class="dica">${esc(i.sugestao)}</div>`}</td></tr>`).join("") +
    `</tbody></table>` + (c.itens.length ? "" : `<p class="dica">Nada para comparar ainda (adicione trechos/narração).</p>`);
}
$("#ref-sel").onchange = () => tentar(async () => { await salvarProjeto({ referencia: $("#ref-sel").value || null }); await compararRef(); });
$("#ref-aplicar").onclick = () => tentar(async () => {
  const id = $("#ref-sel").value; if (!id) throw new Error("escolha um perfil");
  const antes = fotografia();
  const r = await api("POST", `${base()}/referencia/${id}/aplicar`);
  historico.antes.push(antes); historico.depois = []; atualizarBotoesHistorico();
  P = r; renderTudo(); renderGuia(); await compararRef();
  aviso("Aplicado: " + (r.mudancas.join(", ") || "nada a mudar") + ". Ctrl+Z desfaz.");
});
