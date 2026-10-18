// Clipador - estado global, utilidades (api, aviso, tarefas) e desfazer/refazer.
// Script classico: compartilha o escopo global com os outros js/*.js (ordem no index.html).

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
let P = null;            // projeto atual (estado vindo do servidor)
let segSel = -1;         // segmento selecionado na timeline
let marca = { ini: null, fim: null };

// ------------------------------------------------------------------ utilidades
async function api(metodo, url, corpo) {
  const op = { method: metodo, headers: {} };
  if (corpo instanceof FormData) op.body = corpo;
  else if (corpo !== undefined) { op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(corpo); }
  const r = await fetch(url, op);
  const txt = await r.text();
  let d; try { d = JSON.parse(txt); } catch { d = txt; }
  if (!r.ok) throw new Error((d && d.detail) || txt || r.statusText);
  return d;
}
const base = () => `/api/projetos/${encodeURIComponent(P.nome)}`;
const arq = (rel) => `${base()}/arquivo?caminho=${encodeURIComponent(rel)}&t=${Date.now()}`;
const mmss = (s) => { s = Math.max(0, s || 0); return `${String(Math.floor(s / 60)).padStart(2, "0")}:${(s % 60).toFixed(1).padStart(4, "0")}`; };
const esc = (t) => String(t ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Regiao ao vivo sempre presente (leitores de tela anunciam). Erros e avisos com acao ficam ate fechar.
function aviso(msg, erro = false, acao = null) {
  const bt = $("#aviso-acao");
  $("#aviso-texto").textContent = msg;
  $("#aviso").className = erro ? "erro" : "";
  bt.hidden = !acao;
  if (acao) { bt.textContent = acao.rotulo; bt.onclick = () => { fecharAviso(); acao.fn(); }; }
  if (erro) { const al = $("#aviso-alerta"); al.textContent = ""; setTimeout(() => (al.textContent = msg), 50); }
  clearTimeout(aviso.t);
  if (!erro && !acao) aviso.t = setTimeout(fecharAviso, 3500 + Math.min(msg.length * 40, 4000));
}
function fecharAviso() { clearTimeout(aviso.t); $("#aviso").className = "aviso-vazio"; }
$("#aviso-fechar").onclick = fecharAviso;
async function tentar(fn) { try { return await fn(); } catch (e) { aviso(e.message, true); console.error(e); } }

// acompanha uma tarefa em segundo plano mostrando a barra no elemento `alvo`
async function acompanhar(tarefa, alvo) {
  const el = $(alvo);
  el.className = "tarefa";
  while (true) {
    const t = await api("GET", `/api/tarefas/${tarefa.id}`);
    if (t.estado === "erro") { el.className = "tarefa erro"; el.textContent = "Erro: " + t.erro; throw new Error(t.erro); }
    if (t.estado === "cancelada") { el.className = "tarefa"; el.textContent = "Cancelado."; throw new Error("tarefa cancelada"); }
    const pct = Math.round(t.progresso * 100);
    const tempo = t.decorrido != null ? ` · ${Math.round(t.decorrido)} s` + (t.restante != null ? ` (faltam ~${t.restante} s)` : "") : "";
    el.innerHTML = `${esc(t.mensagem || (t.estado === "na_fila" ? "aguardando outra tarefa terminar…" : "processando…"))} — ${pct}%${tempo}
      <button class="mini" data-cancelar="${t.id}">Cancelar</button><div class="barra"><div style="width:${pct}%"></div></div>`;
    if (t.estado === "ok") { el.textContent = "Concluído."; return t.resultado; }
    await new Promise((r) => setTimeout(r, 700));
  }
}
document.addEventListener("click", (e) => {
  const id = e.target.dataset && e.target.dataset.cancelar;
  if (id) tentar(() => api("POST", `/api/tarefas/${id}/cancelar`));
});

// ------------------------------------------------- desfazer / refazer (Ctrl+Z / Ctrl+Y)
const EDITAVEIS = ["segmentos", "layout", "gancho", "legenda", "audio", "roteiro", "marca", "comparacao", "publicacao"];
const historico = { antes: [], depois: [] };
const fotografia = () => structuredClone(Object.fromEntries(EDITAVEIS.map((k) => [k, P[k]])));
function atualizarBotoesHistorico() {
  $("#desfazer").disabled = !historico.antes.length; $("#refazer").disabled = !historico.depois.length;
}
async function voltarPara(pilhaDe, pilhaPara, nome) {
  if (!pilhaDe.length) return;
  const alvo = pilhaDe.pop(); pilhaPara.push(fotografia());
  P = await api("PUT", base(), alvo); renderTudo(); atualizarBotoesHistorico(); aviso(nome);
}
const desfazer = () => tentar(() => voltarPara(historico.antes, historico.depois, "Desfeito."));
const refazer = () => tentar(() => voltarPara(historico.depois, historico.antes, "Refeito."));
