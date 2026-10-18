# Clipador — revisão de PO + Tech Lead e plano de evolução (17/10/2026)

**Base da revisão.** 13 skills de social media (`youtube-shorts`, `short-form-video-script`, `hook-writer`,
`tiktok-script`, `reels-script`, `captions-and-clipping`, `youtube-publishing-and-metadata`, `thumbnail-design`,
`cross-platform-repurposing`, `platform-specs-and-validation`, `hashtag-strategy`, `caption-writer`,
`viral-reverse-engineering`); recomendações do agente que produziu 14 Shorts reais com o app
(`MELHORIAS_PENDENTES_2026-10-17.md`); medição do código (tamanho, rotas, funções longas, gravações sem trava).

## 1. Visão de produto (PO)
**Para quem:** criador de games que não aparece (ou só narra/reage), publica no YouTube (Shorts + longos), TikTok e Reels.
**Promessa:** do vídeo bruto a um vídeo **que não é pulado** e **pronto para publicar em cada rede**, sem sair do app.
**O que as skills dizem que decide o alcance** (e o app deve medir e cobrar, sem prometer views):
- **Shorts/TikTok/Reels:** o primeiro 1–3 s em três canais ao mesmo tempo (imagem + texto na tela + fala), troca de
  imagem a cada 2–4 s, legenda queimada (≈80% assistem mudo), **final que volta ao início (loop)**, duração bimodal
  (< 30 s ou ~50–60 s), um assunto só.
- **Descoberta é busca:** a palavra-chave dita, escrita na tela e na legenda do post ("menção tripla").
- **Publicação correta por rede, de primeira:** campos obrigatórios, limites (Instagram: 5 hashtags), declarações
  verdadeiras (feito para crianças, conteúdo alterado/IA), sem marca d'água, capa escolhida.
- **Um vídeo longo vira vários Shorts** — cada um com gancho próprio e uma ponte de volta ao longo.

### Lacunas (PO)
| # | Lacuna | Fonte | Impacto |
|---|---|---|---|
| P1 | Não mede retenção: gancho nos 3 s, plano longo demais, duração, loop, CTA genérico | youtube-shorts, short-form-video-script, tiktok-script | alto |
| P2 | Publicação = um campo para todas as redes; sem limites, tags, privacidade, "feito para crianças", aviso de IA, crédito, capa, palavra-chave | youtube-publishing, platform-specs, caption-writer, hashtag-strategy, reels-script | alto |
| P3 | Sem teste de ganchos (duplicar projeto) | hook-writer | médio |
| P4 | Coisas que o agente de produção teve de fazer FORA do app: quadro congelado, exportar sem áudio | agente §1, §3 | médio |
| P5 | Trecho que atravessa um corte de cena passa sem aviso | agente §7 | médio |
| P6 | Revisão "sem som" não é um passo | short-form-video-script | baixo |

## 2. Diagnóstico técnico (Tech Lead)
| # | Achado | Evidência | Risco |
|---|---|---|---|
| T1 | **Gravação do projeto sem trava** e sem nova tentativa: 36 `projeto.salvar` no `app.py`, 19 tarefas em segundo plano; no OneDrive o `os.replace` falha (`PermissionError`) | agente §7 | **perda de edição / erro na tela** |
| T2 | **`app.py` monolítico**: 1.931 linhas, 102 rotas, regra de negócio dentro das rotas (Shorts, zoom nos picos, ritmo, lote…) | contagem | alto custo de manutenção; cada agente lê 2 mil linhas |
| T3 | **`app.js` monolítico**: 2.626 linhas, ~340 funções, num arquivo só | contagem | idem; mudanças pequenas ficam caras e arriscadas |
| T4 | Sem linter/checagem estática; 4 arquivos com BOM | análise | erros bobos só aparecem em uso |
| T5 | Funções longas: `render.montar_comando` 172 linhas, `legendas.gerar_ass` 116 | AST | médio (mexer quebra fácil) |
| T6 | Suíte com ~190 testes em ~5 min, sem separação rápida/lenta | CLAUDE.md | médio (ciclo de feedback lento) |

## 3. Plano desta rodada (ordem de execução) — ✅ tudo feito em 17/10/2026 (detalhes: AUDITORIA.md §15)
1. **T1** trava por projeto + nova tentativa no `projeto.salvar`; helper `projeto.alterar(nome, fn)` para tarefas.
2. **T2** `app.py` dividido em módulos de rota por domínio (`APIRouter`), sem mudar nenhuma URL; regras de negócio
   que estavam nas rotas vão para `core/`. Guarda: a suíte inteira tem de continuar passando.
3. **T3** `app.js` dividido em arquivos por área (mesmo escopo global, ordem de carga fixa). Guarda: abrir todas as
   abas no navegador sem erro no console + testes de interface lendo todos os arquivos.
4. **T4** teste de qualidade estática (compila tudo, sem BOM, sem definição duplicada, sintaxe de todo JS).
5. **P2 Pacote de publicação** por rede (YouTube/TikTok/Reels) com validação, palavra-chave (menção tripla),
   declarações, crédito, ponte para o longo, `.txt` ao lado do FINAL e **capa** (quadro escolhido).
6. **P1 Checklist de retenção** no verificador (medido; nunca "previsão de views").
7. **P3** duplicar projeto · **P4** quadro congelado + exportar sem áudio · **P5** aviso de corte de cena · **P6** sem som.

**Incorporado do agente de produção (§9 das recomendações, lote 3):** botão **"fechar o loop"** (repete o 1º plano
no fim e estica a última legenda — feito à mão em 3 vídeos) entra junto do checklist de retenção (item 6); a ficha de
publicação ganha **título ≤ 70 caracteres** e exportação **`PUBLICACAO.md`** (item 5); "validar antes de renderizar"
e **duração mínima por plano conforme o formato** entram no verificador (itens 6/7).

## 4. Depois desta rodada
✅ **T5** quebrar `render.montar_comando` e `legendas.gerar_ass` em partes testáveis; ✅ **T6** marcar testes lentos
(`-m "not lento"` para o ciclo rápido) — feitos em 17/10/2026, AUDITORIA.md §16. Miniatura do longo (1280×720, legível em 168×94, 3 conceitos para Test & Compare); preset "comentado" e gravar
narração só de um intervalo; emoji na legenda; pasta "vídeos prontos"; cache de cenas entre projetos; tradução de
legendas + cobrir texto queimado; efeito retrô PS1→PS5; parear cenas A×B; anotações (seta/círculo) e inserir meme;
"teardown" de um Short de referência (viral-reverse-engineering: mecanismo, não cópia); separar testes rápidos/lentos.

## 5. Fora do escopo (decisão)
Publicar direto nas redes (exige login/chaves de cada rede; o app entrega arquivo + texto validado) e qualquer
"nota de viralização" (as skills proíbem prometer métricas).
