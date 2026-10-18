# 06 — Auditoria do Clipador (Fase 7)

Estado inicial registrado em 18/10/2026: **233 testes passando** (suíte inteira, ~6–13 min; ciclo rápido
`-m "not lento"` 173 testes); backup `_versoes/clipador_automacao_20261018-1341.zip`. O Git do PC foi consertado
(usuário, 18/10), mas **esta pasta ainda não é um repositório** (`git status` → "not a git repository").
Reversão hoje: zips em `_versoes/`. Revisões anteriores: `docs/AUDITORIA.md` §1–§16 (inclui a auditoria com
`ponytail-audit` de 18/10, 4 achados corrigidos).

## Mapa da arquitetura (VERIFICADO no código)

```
navegador ── web/static (index.html + js/*.js, 17 scripts por aba) ──HTTP──► web/app.py (segurança: Host local,
                                                                              recusa comando de outro site)
CLI ── python -m clipador montar|finalizar|referencia (automacao.py, mesma API em processo)      │
                                                                                                ▼
                                    web/rotas/*.py (13 APIRouters) ─► web/comum.py (validações de entrada)
                                                                                                │
core/: projeto (JSON + trava) · midia/destaques (FFmpeg, cenas, momentos) · timeline · layouts · zoom ·
       legendas (Whisper, ASS) · audio (4 trilhas, mix) · render (FFmpeg, .tmp + ffprobe) · verificador
       (qualidade + retenção) · publicacao (por rede) · referencias (perfis de canal e de vídeos locais) ·
       pedido (clipar pela fala) · kits · react (câmera, recorte IA) · comandos (Command Center) ·
       ia/ (Claude, OpenAI, Gemini, Ollama; chaves no cofre; consentimento; custo) · tarefas (fila, cancelamento)
disco: projetos/<nome>/ (projeto.json, narracao.wav, legenda, RASCUNHO/FINAL) · referencias/ · kits/ · musicas/ efeitos/
```

## Funcionalidades existentes (✅) e parciais (🟡)

| Área | Situação |
|---|---|
| Projetos curtos (9:16) e longos (16:9), formatos com preset | ✅ |
| Importar vídeo (arquivo/link), cenas, momentos, clipar pelo que é falado | ✅ |
| Timeline: dividir, mover, aparar com ímã, congelar, fechar o loop, editar pela transcrição | ✅ |
| Layouts empilhado, tela cheia (zoom com `perspective`), comparação A×B, React (chroma/recorte IA) | ✅ |
| Áudio: original (volume/mudo por trecho), música, narração (deslocamento), efeitos, ducking, −14 LUFS | ✅ |
| Narração gravada no navegador sobre a prévia; legendas Whisper (karaokê/palavra/caixa), edição manual | ✅ |
| Revisão: quadros, RASCUNHO → aprovação (hash) → FINAL; verificador técnico + retenção | ✅ |
| Publicação por rede, capa, PUBLICACAO.md, declarações do usuário | ✅ |
| Referências: perfil de canal (YouTube) e de vídeos locais (duração, cortes, fala) | ✅ |
| Montagem automática até o RASCUNHO (CLI) | ✅ |
| IA: provedores, consentimento por provedor, histórico só de metadados, custo do Claude | ✅ |
| Narração **gerada** (TTS / clone da própria voz) | ❌ não existe (só gravação do usuário) |
| Banco de ideias, pontuação CPV, roteiros com fontes, ganchos alternativos | ❌ |
| Registro de origem/licença de cada mídia | 🟡 só `ORIGEM.txt` manual em skills; mídia do projeto não tem |
| Verificações de conformidade (matriz 04) | 🟡 parte no verificador e na publicação; faltam originalidade, terceiros, termos de risco, duplicado |
| Estados rastreáveis da esteira (pesquisa → … → análise) | 🟡 CLI faz montar/finalizar sem estado persistente nem prevenção de duplicado |
| YouTube Analytics / publicação | ❌ (exige OAuth do canal do usuário) |
| Gerador de mapas (canal 1) | ❌ |

## Problemas e riscos encontrados

| # | Achado | Evidência | Risco | Prioridade |
|---|---|---|---|---|
| A1 | **Sem controle de versão** nesta pasta | `git status` falha | Mudanças grandes sem reversão fina | P0 |
| A2 | **Sem lista de dependências fixadas** (`requirements.txt` inexistente) | busca de arquivos | Reinstalar o PC quebra versões (fastapi 0.143, yt-dlp 2026.8.19…) | P0 |
| A3 | Projeto atual (GTA 6) usa **trailer da Rockstar** e é orientado a monetizar | política Take-Two (05, fato 3) | Remoção/claim; fora do uso não comercial | P0 (decisão do usuário) |
| A4 | Esteira automática sem **estado persistente** nem **trava contra execução duplicada** | `automacao.py` | Rodar `montar` duas vezes falha por nome; não retoma etapa | P1 |
| A5 | Nenhuma checagem de **similaridade entre roteiros/vídeos do mesmo canal** | — | Risco "inautêntico/repetitivo" (F1) invisível | P1 |
| A6 | Mídia sem **origem/licença** registrada | `projeto.fontes` só tem caminho | Não dá para provar direitos nem calcular % de terceiros | P1 |
| A7 | Aviso de **música × receita do fundo** inexistente | F3 | Receita menor sem o usuário saber | P2 |
| A8 | Shorts > 60 s com material de terceiros não alertados | F3 | Não monetiza com claim | P2 |
| A9 | Sem observabilidade da esteira (log estruturado por etapa) | tarefas em memória | Difícil diagnosticar falhas em lote | P2 |
| A10 | `yt-dlp` sofre **429** em lote de legendas (visto na pesquisa) | Fases 1–3 | Referências por canal podem falhar em massa | P2 (pausas/retomada) |

Segurança (revisada de novo): middleware de Host/Origem ✅; validação de toda entrada que vira parâmetro do
FFmpeg ✅; chaves só no cofre/variável ✅; teste de qualidade estática ✅ (BOM, imports, rotas). Desempenho:
render serializado em fila (1 pesado por vez) — adequado a um usuário. Custos de API: só a IA (opcional, por
consentimento) — registro de custo existe para o Claude; OpenAI/Gemini sem preço fixo no código (por regra do projeto).

## Pontos frágeis da geração automática
1. Sem roteiro: a automação monta vídeo a partir de **trechos de vídeo**, não de uma ideia/roteiro.
2. Escolha de "melhor momento" é por sinais de imagem/áudio; não sabe de narrativa nem de direitos.
3. Nada impede produzir em massa vídeos parecidos (risco F1/F5).
4. Sem fontes ligadas a afirmações (risco factual + feedback do usuário: "você erra muito" em texto).
