# 11 — Relatório final do projeto mestre CPV (18/10/2026)

## Resumo executivo
O Clipador passou de editor de vídeos a **estúdio orientado por evidência**: pesquisa registrada (8 fontes de
ensino, 49 Shorts ≥ 10 mi verificados, 12 páginas oficiais de política), protocolo CPV com pontuação de pesos
fixos, controles de direitos e conformidade em todo projeto, e o ciclo ideia → roteiro → montagem → revisão →
publicação (pelo usuário) → métricas → experimento → finanças. **Nada disso garante viralização, monetização ou
lucro**: aumenta a chance de bons resultados e reduz risco e desperdício.

## Conclusões sustentadas por evidência
- VERIFICADO (oficial): a partir de 01/02/2027 a receita de Shorts exige **10 mi de views de Shorts a cada 90 dias**
  e a entrada nova no YPP dobra (8.000 h ou 20 mi/90 dias). Canal só de Shorts é aposta frágil → Shorts + longos.
- VERIFICADO (oficial): conteúdo templado, reutilizado ou de IA em massa tira a monetização do **canal inteiro**.
- VERIFICADO (Take-Two): material de GTA só para uso **não comercial** → canal 4 sem receita até licença.
- VERIFICADO (medido, 49 Shorts): plano médio de 3,6 s; texto na tela no início em 45%; narrados começam a falar
  no segundo 0 a 144–224 palavras/min e guardam a recompensa para o fim; duração mediana ~45 s.
- Contradições resolvidas pela fonte oficial: horário de postar não é otimizado; apagar e repostar arrisca spam.

## Nichos selecionados (detalhes em 05)
1. **Mapa Esquisito** (geografia, 85/100) · 2. **História Esquisita** (78) · 3. **Como o Espaço Funciona** (74) —
em português, narrados pelo usuário; dublagem automática PT→EN dos longos como alavanca a testar.
4. **GTA 6 Comparado** — separado, sem monetização até licença da Take-Two (rascunho do e-mail pronto).

## Arquivos e módulos alterados/criados (branch `cpv-implementacao`)
Núcleo: `core/recursos.py`, `core/conformidade.py`, `core/estudio.py`, `core/canais.py`, `core/ideias.py`,
`core/roteiros.py`, `core/originalidade.py`, `core/esteira.py`, `core/metricas.py`, `core/experimentos.py`,
`core/financeiro.py`; alterados `core/projeto.py`, `core/verificador.py`, `core/publicacao.py`. Web:
`web/rotas/estudio.py` (novo), `rotas/fontes.py`, `rotas/audio.py`, `static/js/fonte.js`, `static/js/comandos.js`,
`web/app.py`. CLI: `clipador/cli_estudio.py`, `automacao.py`, `__main__.py`. Raiz: `.gitignore`, `requirements.txt`,
`CLAUDE.md`. Docs: `docs/cpv/01–11`, `AUDITORIA.md` §17. Testes: 4 arquivos novos + 1 teste novo em test_qualidade.

## Testes
259/259 passando (08). Não testados por falta de insumo: CSV real do Studio, provedor de IA real, telas do estúdio.

## Pendências e bloqueios
| Pendência | Bloqueio |
|---|---|
| Telas do estúdio (Canais, Ideias, Roteiro, Esteira, Resultados) | só implementação (núcleo/API/CLI prontos) |
| Gerador de mapas (canal 1) | autorização para baixar os dados Natural Earth (domínio público) |
| Validar importador com CSV real | export do canal do usuário |
| Licença Take-Two | resposta da Take-Two (o usuário envia o e-mail) |
| Publicação via API | opcional; OAuth + autorização explícita |

## Custos e riscos relevantes
Custo em dinheiro por Short ≈ centavos (IA opcional ≈ US$ 0,02–0,04 por rascunho); custo real = tempo do usuário
(1–2 h/Short, a medir). Riscos: elegibilidade de 2027; RPM em português provavelmente baixo (alegado); capacidade
de uma pessoa para 3 canais (começar pelo Mapa Esquisito); fatos errados (mitigado: fonte por afirmação).

## Próximas ações (ordem)
1. Revisar os 4 canais criados (estudio/canais) e enviar o e-mail à Take-Two.
2. Primeiro piloto: 1 ideia → roteiro → Short do Mapa Esquisito, do pedido na conversa até o RASCUNHO.
3. Autorizar o download dos dados Natural Earth → gerador de mapas.
4. Telas do estúdio no app.
5. Após 10–30 publicações: importar CSV, ligar experimentos, recalibrar pesos do CPV só com dados do canal.
