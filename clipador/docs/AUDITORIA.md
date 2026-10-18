# Clipador — auditoria, diagnóstico e plano (16/10/2026)

Estado de cada item: **✅ Testado e funcional** · **🟡 Implementado, não validado** · **🔨 Em desenvolvimento** ·
**📋 Planejado** · **⛔ Bloqueado por dependência externa**.

## 1. O que foi analisado
- Todo o código: `clipador/core` (9 módulos), `clipador/web` (FastAPI + HTML/JS/CSS sem build), 2 projetos reais.
- Ambiente: Python 3.13.15, FFmpeg 9.0.2, faster-whisper 1.2.1, FastAPI 0.143, Starlette 1.8, yt-dlp 2026.8.
- Execução real: servidor no ar, fluxos testados no navegador embutido e por API, renders medidos com ffprobe/ebur128.
- **Limitação**: o Git do PC está corrompido (`git.exe` "não é um aplicativo válido"). O estado inicial foi salvo em
  `_versoes/clipador_estado_inicial_20261016-1240.zip`. Reinstalar o Git é decisão do usuário.

## 2. Diagnóstico
**Preservar (funcionava):** núcleo FFmpeg (3 layouts verticais, gancho, 3 estilos de legenda), transcrição
palavra a palavra, cadeia de voz da regra 4, fluxo RASCUNHO → aprovar → FINAL com hash, gravação atômica do projeto.

**Corrigido nesta etapa (todos com teste):**
| Problema | Evidência | Correção |
|---|---|---|
| Qualquer site aberto no navegador podia mandar comandos ao Clipador (CSRF) | POST com `Origin: site-malicioso` → 200 | middleware recusa Origin/Sec-Fetch-Site de outro site (→ 403) |
| DNS rebinding | `Host: evil.example` → 200 | só atende 127.0.0.1/localhost |
| Recorte (`crop`) livre ia direto para o filtergraph (injeção de filtro FFmpeg) | `1:1:0:0,movie=...` aceito | regex + limites no servidor e no render |
| Layout, estilo, trechos e áudio sem validação no servidor | `layout: "rm -rf"` → 200 | validação de tipo e limite em `app.py` e `core/audio.py` |
| FFmpeg podia travar para sempre (stderr não lido enchia o pipe) | tarefa presa + FFmpeg órfão | stderr drenado em thread, vigia de 3 min, cancelamento |
| Arquivo final podia ficar corrompido com o nome definitivo | — | grava em `.tmp`, verifica (duração, trilhas, resolução) e só então renomeia |
| Upload com mesmo nome sobrescrevia | — | `nome (2).ext` |
| Legenda mostrava "bonito!" (pontuação) | teste | limpeza de `!?…` |
| Hash de aprovação lia a narração inteira a cada consulta | — | tamanho + data de modificação |
| Abrir o app com o último projeto apagado mostrava erro | console | ignora em silêncio |

**Refatorado:** áudio passou de 6 chaves soltas para um modelo versionado de 4 trilhas (migração automática,
testada); bibliotecas de música e efeitos com as mesmas rotas; render com camadas de áudio independentes.

**Riscos que continuam:**
- Se o processo do servidor for morto à força, um FFmpeg em andamento pode continuar órfão (Windows não encerra filhos).
- Projetos guardam o caminho absoluto dos vídeos; se o arquivo for movido, o app avisa ("arquivo faltando"), mas não reencontra sozinho.
- A gravação pelo microfone no navegador não foi testada com microfone real nesta sessão.
- Não há autenticação: o app foi feito para uso local (127.0.0.1). Não exponha a porta na rede.

## 3. O que foi implementado (esta etapa)
| Função | Estado | Como foi verificado |
|---|---|---|
| Áudio multipista: original (volume com/sem narração + volume/mudo por trecho), música (entra/sai no vídeo, ponto de entrada, fades, repetir), narração (volume, deslocamento ±, fades, tratamento liga/desliga), efeitos (vários, no instante escolhido, corte, fade) | ✅ | 16 testes medindo cada trilha isolada por frequência no arquivo final |
| Ducking leve/média/forte; efeitos não são abaixados | ✅ | teste mede ≥ 6 dB de queda da música durante a fala |
| Silenciar o original não altera o vídeo | ✅ | MD5 dos quadros decodificados idêntico |
| Pré-escuta da mixagem e **solo por trilha**, com aviso de prévia desatualizada | ✅ | teste + navegador |
| Detecção de clipping/volume baixo da narração | ✅ | teste com áudio estourado |
| Timeline de áudio visual (4 pistas, trechos, fades, cursor, M/S) + painel por trilha com salvamento automático | ✅ | navegador (cliques reais via JS) |
| Desfazer/refazer (Ctrl+Z / Ctrl+Y), atalhos (Alt+1…7, Espaço, Esc), estado de foco visível | ✅ | navegador |
| Tarefas com tempo decorrido, estimativa restante e **Cancelar** | ✅ | teste de cancelamento real |
| Áreas **Vídeos curtos** e **Vídeos longos** na barra lateral | ✅ | navegador |
| Formatos **Guias, Notícias, Gameplay, Curiosidades, Compilados** (curto e longo) com preset, guia, roteiro-modelo e checklist baseados em pesquisa | ✅ | 9 testes + navegador |
| Vídeo longo 1920×1080 (fonte nítida + fundo desfocado + zoom) | ✅ | render real verificado (ffprobe) |
| Ranking 1…N revelado a cada trecho (compilados) | ✅ | teste da ordem + quadros conferidos |
| Capítulos do YouTube (cartela na tela + texto para a descrição, com regras ≥3 e ≥10 s) | ✅ | testes |
| Gravação de narração no navegador sobre a prévia | 🟡 | código revisado; falta teste com microfone real |

## 4. Testes
`python -m pytest tests -q` → **57 passando** (≈75 s). Todos usam mídia **real** gerada pelo FFmpeg e FFmpeg real;
nenhum mock. Arquivos: `test_legendas.py` (8), `test_render.py` (10), `test_audio.py` (16), `test_api.py` (14),
`test_formatos.py` (13). Projetos de teste ficam numa pasta temporária, nunca em `projetos/`.
Não coberto por teste automático: transcrição Whisper (lenta; testada manualmente), gravação pelo microfone, UI por
clique real de mouse (testada por eventos no navegador).

## 5. Plano por fases (ordem ajustada pela auditoria)
| Fase | Conteúdo | Estado |
|---|---|---|
| 1 Auditoria e estabilização | diagnóstico, baseline, testes, segurança | ✅ |
| 4 Áudio e legendas | 4 trilhas, prévia, ducking, clipping; legendas: presets TikTok/Shorts/Reels (posição na área livre, tamanho, cores, animação pop — recomendações editáveis, não regras oficiais), visual personalizável (fonte, tamanho, contorno, sombra, cores), tempo por palavra com ouvir/ajustar, exportação .srt (com deslocamento, sem sobreposição) | ✅ (8 testes + navegador) |
| 2 Nova interface | áreas curtos/longos, formatos, desfazer, atalhos | ✅ parcial — 📋 arrastar e soltar arquivos, painéis redimensionáveis |
| 3 Motor de edição | ✅ timeline de vídeo (aba Cortes): miniaturas, arrastar para reordenar (solta onde está o ponteiro), aparar pelas bordas com ímã nos cortes de cena, dividir no cursor (S), duplicar (D), remover (Delete), zoom, reprodução contínua da montagem, ← → no cursor, desfazer; arrastar e soltar arquivos (vídeo → fonte, áudio → músicas). Operações no servidor em `core/timeline.py` (5 testes, inclusive render após editar) · 📋 multipista de vídeo (sobreposições/B-roll) para longos, seleção múltipla |
| 5 Gravação e composição | ✅ aba 9 · React: câmera + microfone gravados no navegador sobre a prévia (pausar/retomar), microfone vira a narração, janela sobreposta (arrastar, tamanho, retângulo/círculo/vertical), tela dividida (curtos), fundo virtual, chroma key (+ reduzir reflexo verde), sincronia ±, importar vídeo de câmera — mecânica testada em pixels (16 testes). 🟡 recorte por IA sem tela verde (MediaPipe local): pipeline e render testados, mas **a qualidade em pessoas reais não foi validada** (sem câmera/pessoa nos testes) · 🟡 gravação pelo microfone/câmera do navegador: código revisado, não testado com hardware real · 📋 gravar a tela em vez da câmera |
| Destaques (ideias do OpusClip, ver `ANALISE_OPUSCLIP.md`) | ✅ aba Cortes · Momentos: janelas de N s com nota relativa e motivos medidos (volume, impactos sonoros, movimento, ritmo de cortes, gancho), início no corte de cena; usar na timeline (dividido nos cortes); 🎯 foco automático pelo centro do movimento; um projeto por momento em lote. Sinais em cache (`cache/<fonte>/sinais.npz`). 9 testes com vídeo sintético de posição/tempo conhecidos + trailer real (2,6 s de análise) · ✅ clipar por pedido: transcrição local da fonte (Whisper, idioma automático, cache) + busca na fala sem acento/por radical, ou IA (só texto: transcrição + momentos medidos, prévia exata e confirmação; resposta validada) · ✅ editar pelo texto: palavras da montagem, seleção e corte (`timeline.cortar_intervalo`) · ✅ kit do canal (legenda, layout, logo, referência, mixagem; no projeto novo ou aplicado depois) + logo no render dentro da área segura · ✅ versão 1:1 de RASCUNHO/FINAL (faixa gancho→legenda; se não couber, laterais desfocadas) — 10 testes, inclusive Whisper real com voz pt-BR do Windows e pixels do logo · 🟡 pedido por IA: só testado sem provedor (falta chave real) · 📋 intro/outro no kit |
| 6 Modos de longos | 🟡 base pronta (formatos longos + 16:9 + capítulos) · 📋 React / Gameplay com webcam / Canal Dark com imagens e TTS |
| 7 IA | ✅ provedores Claude/OpenAI/Gemini/Ollama, chaves no cofre do Windows, consentimento, limites, histórico, assistente (títulos/ganchos/descrição/hashtags, roteiro, revisão), perfis de referência + comparação (ver §7) · 📋 sugestão de cortes por IA (precisa enviar dados de cena), medição visual automática de referências |
| 8 Segurança/otimização | ✅ parcial (acima) · 📋 encerrar FFmpeg órfão com Job Object, limpeza de temporários antigos |
| 9 Validação final | contínua a cada etapa |

**Dependências externas:** chaves de API para a fase 7 (assinatura de chatbot ≠ acesso à API); Git funcionando para
versionamento; trilhas/efeitos com direito de uso fornecidos pelo usuário.

## 7. Fase 7 — IA e referências (16/10/2026)
| Função | Estado | Verificação |
|---|---|---|
| Chaves no Gerenciador de Credenciais do Windows (keyring), nunca devolvidas inteiras (••••1234), nunca em arquivo/log | ✅ | teste real no cofre (serviço de testes separado) |
| Claude (SDK `anthropic`, padrão `claude-opus-5-5`, effort medium, saída JSON por schema, fallback de recusa `"default"`), OpenAI (SDK `openai`, Responses API), Gemini (SDK `google-genai`), Ollama local | 🟡 sucesso **simulado** por servidor local que imita cada API; ✅ erro real de chave inválida nas 3 APIs oficiais | sem chave real não há como validar uma resposta real — validar ao configurar a sua chave |
| "Testar conexão" lista modelos sem gastar tokens; modelos de OpenAI/Gemini não são fixos no código (lista vem da conta) | ✅ simulado + erro real | |
| Consentimento por provedor, prévia exata do texto enviado, vídeo/áudio nunca enviados | ✅ | teste + navegador |
| Limite diário, orçamento mensal (só custo conhecido: tabela oficial da Anthropic), histórico só com metadados (conteúdo só com opt-in), apagar histórico | ✅ | testes |
| IA indisponível não bloqueia edição manual | ✅ | teste |
| Perfil de referência "Davy Jones GTA 6" (2 canais oficiais, 102 Shorts + 82 longos, 26 detalhados, 3 Shorts medidos visualmente) | ✅ dados observados | `referencias/davy-jones-gta-6.json` |
| Gerar perfil de qualquer canal (metadados + ritmo de fala pela legenda automática, texto descartado) | ✅ (rodado de verdade no canal acima) | |
| Comparar projeto × referência (duração, cortes/min, fala, título, capítulos, gancho) e aplicar parâmetros | ✅ | testes + navegador |

**Achados do perfil Davy Jones (observados):** Shorts com 23–29 s (mediana 25 s); fala muito rápida (~234 palavras/min,
~10–13 palavras nos 3 primeiros segundos, começa a falar no segundo 0); Shorts de jogo/notícia com corte a cada ~1–1,5 s
(39–64 cortes/min), tela cheia e legenda de 1–3 palavras com palavra-chave colorida; Shorts de opinião usam o rosto
(fora do modelo sem aparecer); longos com mediana de ~11 min, 78% dos títulos em MAIÚSCULAS e números; publica a cada
~2 dias. **Amostra visual pequena (3 vídeos).**

## 8. Revisão de interface (16/10/2026) — skills better-* + heurísticas de Nielsen
Método: auditoria no app real (todas as abas + 3 diálogos, em 320 px e desktop), contraste **medido** (não estimado) e leitura do HTML/CSS/JS.
| Heurística | Achado (antes) | Mudança (agora) |
|---|---|---|
| 1 Visibilidade do estado | nenhuma pista do que já foi feito | abas com ✓/• por etapa + faixa **"Próximo passo"** com botão que leva à aba certa |
| 2 Linguagem do usuário | "ímã", "altura (y)", "Whisper small" | "Grudar nos cortes", "Altura da legenda", "Rápido / Mais preciso" |
| 3 Controle e liberdade | `confirm()` ao trocar a timeline (ação reversível) | sem pergunta: aviso com **Desfazer**; confirmação só no que não volta (criar projetos, enviar à IA, aprovar) |
| 4 Consistência | Estilo exigia "Salvar", o resto salvava na hora; dois cartões "Timeline" | Estilo salva na hora; segundo cartão virou "Trechos da montagem" |
| 5 Prevenção de erros | microfone pedido sozinho ao abrir a aba; atalhos (Espaço, S, D) sequestravam botões | microfone só em "Ativar microfone"; atalhos de uma tecla só com o foco na timeline (WCAG 2.1.4) |
| 6 Reconhecimento | atalhos num aviso de 3 s | diálogo de atalhos (⌨); instruções longas dentro de "Como usar a timeline" |
| 7 Eficiência | 9 abas planas | 7 etapas numeradas + "Extras" (Assistente, React); Alt+1…9 mantidos |
| 8 Minimalismo | aba Cortes com 5 blocos empilhados | coluna esquerda em 2 modos: **Cenas do vídeo** / **Momentos automáticos** |
| 9 Erros | erro sumia em 9 s | erro/aviso com ação ficam até fechar; região ao vivo anuncia para leitor de tela |
| 10 Ajuda | tela vazia seca | boas-vindas + guia do formato + "Próximo passo" |

Acessibilidade/layout/cor/tipografia: 22 controles sem nome → 0 (mais 5 nos diálogos); cenas, saídas, projetos e trilhas de áudio viraram **botões** (alcançáveis por teclado); foco visível nos cartões de radio escondido; contraste medido — texto branco sobre o botão Gravar 3,59:1 → 6,09:1 e borda de campos 1,33:1 → ≥3,9:1; fontes em `rem` e nunca abaixo de 12 px; 320 px: coluna principal 140 px → 320 px, sem rolagem lateral nas 9 abas; movimento reduzido respeitado.
Guardas automáticas: `tests/test_interface.py` (nomes acessíveis, contraste dos tokens, fontes, atalhos, microfone, abas × painéis).
🟡 Não verificado: leitor de tela real, Tab por todos os diálogos, toque real em celular, zoom de 200 % medido, tema claro (só existe o escuro). 📋 Posicionar o cursor da timeline de áudio só pelo mouse (há campos numéricos como alternativa).

## 9. Prévia da timeline sem trava no corte (17/10/2026)
Problema: a reprodução da montagem (aba Cortes) travava em cada corte. Medido num projeto de 6 trechos não vizinhos (16 s):
**17,2 s** para tocar (≈240 ms de trava por corte) e o vídeo passava **204 ms** do ponto de corte (o fim do trecho era detectado por `timeupdate`, ~4×/s; e o corte "pulava" `currentTime` no mesmo player, o que obriga o navegador a decodificar desde o quadro-chave).
Correção (`app.js`, `tocarTimeline`/`vigiarTL`/`avancarTL`): **dois players** alternados (`#player-fonte` e `#player-fonte-b`); o próximo trecho já fica posicionado no outro player e o corte só troca qual está visível; o corte é detectado por quadro (`requestAnimationFrame`) com `setTimeout` de segurança para aba oculta; trechos vizinhos (fim = início do próximo) nem trocam de player.
Depois: **16,18–16,25 s** (≈ 0–10 ms por corte, o resto é o arranque do 1º play) e **0 ms** além do corte. Parar no meio devolve o player principal, na mesma posição.
Também corrigido: o servidor passou a mandar `Cache-Control: no-cache` em `/` e `/static/*` (antes o navegador podia misturar `app.js` velho com `index.html` novo até um Ctrl+F5).
🟡 Não verificado: o *render* final (FFmpeg) não mudou — esta correção é só da prévia no navegador; trocas entre fontes diferentes foram medidas só com a mesma fonte.

## 10. Missão "auditoria, correção e evolução" (17/10/2026)
| Área | Causa encontrada | O que mudou | Verificação |
|---|---|---|---|
| Gravação/prévia | o player da prévia recarregava (e voltava ao zero) a cada redesenho da tela; nada avisava que a prévia era de uma montagem antiga; não dava para ouvir a narração com a prévia; render salvava o projeto inteiro e apagava edições feitas durante ele | player só recarrega quando a prévia muda (`proxy_versao`); selo "em dia/desatualizada" (`hash_previa`); "Tocar a prévia com a narração" sincronizado; render grava só a sua marca | 5 testes + navegador com microfone simulado (gravar → ouvir → salvar) |
| Legendas | só da narração; sem VTT; sem prévia ao vivo; "Salvar correções" quebrava com o painel de tempos aberto | origem **narração ou áudio do vídeo** (no relógio da montagem); `.vtt`; prévia ao vivo sobre a prévia; `*palavra*` + "Destacar palavras importantes" | 5 testes (Whisper real com voz pt-BR) + navegador (posição 46,3%/61,5% = render) |
| React | prévia com câmera em loop solta do jogo; chroma da prévia em RGB (≠ FFmpeg); recorte IA invisível; fundo virtual fixo; bordas da IA borradas; faixa preta no palco | composição sincronizada (Tocar/barra); chroma com a conta do FFmpeg (erro médio de alfa 0,127 → 0,052); máscara real da IA na prévia; posição/tamanho do fundo virtual; filtro guiado + refinamento/borda/estabilidade; despill pela cor | 3 testes novos + 16 antigos + navegador (câmera = fundo − 1 s; 95,1% recortado) |
| Zoom | escada de 2 px + recorte inteiro (tremor 1,1 px/quadro), sempre linear até o fim, só para o centro, sem zoom no empilhado | `core/zoom.py`: presets (destaque, impacto, reação, lento), início/duração/curva/volta, ponto de destaque X/Y; `perspective` subpixel (tremor 0,25 px, erro < 1,1 px); empilhado zoomeia só o bloco; prévia exata do trecho; zoom só nos picos | 5 testes (render real com posição medida) |
| Command Center | — | barra "Diga o que fazer" (Ctrl+K): regras em PT → plano → executar ações do catálogo (`core/comandos.py`); IA opcional só escolhe ações; nada roda sem clicar | 15 testes (efeito real no projeto, proteções) + navegador |
| Ferramentas | — | verificador pré-exportação (pretos, congelado, silêncio, volume, legenda × vídeo…); assistente de ritmo (pausas, com "talvez manter"); formatos longos com padrões observados | testes + pesquisa em `PESQUISA_REFERENCIAS_2026-10.md` |
| Servidor | navegador misturava `app.js` velho com HTML novo | `Cache-Control: no-cache` em `/` e `/static/*` | teste |

🟡 Não verificado com hardware/pessoa real: microfone e câmera físicos (simulados), qualidade do recorte por IA em pessoas, IA do Command Center com chave real (sem chave neste PC). ✅ Biblioteca de estilos (§11). 📋 Exportar como MCP.

## 11. Biblioteca de estilos — item E (17/10/2026) ✅
Antes: o kit do canal só era salvo a partir de um projeto aberto, aplicado ou excluído; zoom só com os 4 presets embutidos.
| O que | Onde | Regras |
|---|---|---|
| Janela **🎨 Biblioteca de estilos** (barra lateral, funciona sem projeto; também em 3 · Estilo → “Biblioteca de estilos…”) | `index.html #dlg-kits`, `app.js abrirBiblioteca` | editar e clicar **Salvar kit** (formulário explícito; trocar de kit com mudança não salva pergunta antes) |
| Kit em branco, duplicar, renomear, editar (nome, layout curto, legenda completa, logo, gancho, zoom padrão) | `core/kits.py` `novo/duplicar/atualizar`; rotas `POST /api/kits` (sem `projeto`), `GET/PUT /api/kits/{id}`, `POST /api/kits/{id}/duplicar` | `app._validar_kit` (mesmas regras do PUT do projeto; campo desconhecido = 400; nada é gravado se um campo falhar). Renomear troca o arquivo; nome de outro kit = 409 (não sobrescreve). Duplicar nunca sobrescreve (`-2`, `-3`…). Salvar do projeto por cima de um kit mantém o zoom padrão dele |
| Zoom padrão no kit | `kit.zoom_padrao` = efeito completo validado por `zoom.validar` (preset + valores + ponto) | kits antigos carregam com `None` |
| “Zoom do kit nos trechos sem zoom” (3 · Estilo) | `POST /api/projetos/{n}/kit/zoom`, `kits.aplicar_zoom` | só trechos sem `zoom_fx` e sem o zoom antigo; layout comparação/dividido = 400; aviso com **Desfazer** (+ Ctrl+Z) |
| Presets de zoom do usuário | `zoom.salvar_preset/remover_preset/todos`, arquivo `kits/zoom/presets.json`; rotas `POST/DELETE /api/zoom/presets` | nome de embutido/“personalizado” recusado; valores pelos limites do `zoom.validar`; máx. 50. Aparecem no menu Zoom de cada trecho; “Salvar como preset” na linha do zoom do trecho. Excluir não muda vídeo nenhum: o trecho guarda os valores e vira “personalizado” |
| Desfazer do logo | `EDITAVEIS` inclui `marca` | antes, Ctrl+Z depois de “Aplicar kit” não voltava o logo |

Defeito achado na verificação e corrigido: o arquivo de presets ficava em `kits/zoom_presets.json` e aparecia como um kit sem nome (e um kit com esse nome poderia sobrescrevê-lo). Agora fica numa subpasta e `kits.carregar` recusa JSON que não é kit.
Verificação: suíte inteira 177 passando (172 + 5 novos em `tests/test_biblioteca_estilos.py`: API real + render real com o zoom do kit) e navegador (servidor de teste na porta 8766): criar → editar → renomear → duplicar → preset de zoom → aplicar o zoom do kit num projeto → Desfazer → salvar zoom do trecho como preset.
## 12. Atualizar legendas e limite no fim do vídeo (17/10/2026) ✅
- **🔄 Atualizar legendas** (aba Legendas e na faixa de aviso): transcreve de novo com a mesma origem; sem confirm. A versão anterior fica em `legenda_cartoes.anterior.json` e o aviso tem **Desfazer** (`POST .../legendas/restaurar`, que troca; clicar de novo refaz). O “Transcrever” usa o mesmo fluxo.
- **Desatualizada**: `projeto.base_legenda` (trechos + fontes no áudio do vídeo; arquivo da narração) gravada em `legenda_base`; `_estado.legendas_desatualizadas` → faixa de aviso + “Próximo passo”.
- **Nunca maior que o vídeo**: `legendas.limitar` na geração (`fora_do_video` informado), no `.ass`, no SRT/VTT; a cauda de 0,12 s do último cartão passava 0,12 s do fim (corrigido em `gerar_ass`). `_estado.legendas_passam` só conta cartões que entram no vídeo (sem narração = só provisórios; o alarme falso foi visto no projeto real e corrigido).
- Testes: `tests/test_legendas_atualizar.py` (4, um com voz pt-BR do Windows + Whisper real). Suíte: 181 passando.
- 📋 Não feito: refazer sozinho em segundo plano a cada mudança (o Whisper leva segundos a minutos e apagaria correções sem você ver).

## 13. Comparação A × B com dois vídeos (17/10/2026) ✅
Problema relatado: o layout “Comparação A × B” existia, mas não havia onde escolher os 2 vídeos; cada trecho usava o mesmo vídeo em cima e embaixo (parecia sem divisão), e a prévia mostrava um vídeo só.
- **Formato novo “⚖️ Comparação A × B”** (só no curto, `formatos.SO_CURTO`): layout comparação, gancho “GTA 5 × GTA 6”, guia próprio. Não é React (sem câmera).
- **`projeto.comparacao`** = `fonte_a`, `fonte_b`, `rotulo_a/b`, `audio` (a | b | ambos), `divisoria`; validado em `app._validar_comparacao`. Num projeto de comparação o 1º vídeo adicionado vira o A e o 2º o B. Remover um vídeo limpa a referência.
- **Cartão na aba 1 · Fonte**: escolher A (em cima) e B (embaixo), trocar, rótulos, som, linha; **Montar comparação** (`POST .../comparacao/montar`, com Desfazer); **▶ Ver lado a lado** (os 2 vídeos no mesmo instante, tarjas cortadas como no render).
- **Trechos**: trecho novo já entra com o B padrão e `ini_b` que cabe no B; B que passa do fim do vídeo B = 400. Na aba Cortes: “B começa em”, enquadrar A/B e **▶ Prévia exata**.
- **Render**: B padrão do projeto (`render.fonte_b_do_trecho`); som do A, do B ou dos dois (`amix`); B mais curto congela no último quadro (`tpad`) em vez de quebrar; rótulos padrão no .ass. Config só entra no hash quando o layout é comparação (não invalida aprovações antigas).
- Testes: `tests/test_comparacao.py` (4; cor de cada metade, linha, troca A/B e frequência do som medidas no resultado real). Navegador: servidor de teste numa pasta temporária, quadro real conferido. Suíte: 185 passando.

## 14. Editor A × B, aba 6 · Textos e “excluir o que deu errado” (17/10/2026) ✅
Relato do usuário: não dava para cortar os 2 clipes com o mesmo tempo nem nos trechos certos; não achou como tirar o “VOCÊ SABIA DISSO?”; não dava para excluir o rascunho; faltava editar legendas.
- **Editor A × B** (aba 2 · Cortes, só no layout comparação): dois players lado a lado, ◀/▶ quadro a quadro, Início/Fim do A e Início/Fim do B; os dois têm **sempre a mesma duração** (Fim B ajusta o Fim A); “B acompanha o A”; **▶ Tocar os dois** (espera os dois posicionarem e corrige o B pelo relógio do A: diferença medida ≤ 0,03 s); **+ Adicionar à montagem**; clicar num trecho da lista abre as marcas dele (“Salvar no trecho N”).
- **Aba 6 vira “Textos”**: título do início (com ✕ Tirar e “Usar sugestão”), rótulos A/B, legendas e visual num lugar só. **Editar no próprio vídeo**: título, legenda e rótulos desenhados sobre a prévia são botões; clicar abre um editor no lugar (Enter salva, Esc cancela, 🗑 Excluir). “+ Legenda aqui” escreve uma legenda no instante do vídeo; “+ Adicionar legenda”, ✕ por cartão, “Excluir todas”, ▶ leva o vídeo ao cartão. Gerar a prévia direto na aba.
- **Formato não escreve mais texto sozinho**: o gancho do preset virou sugestão (`guia.sugestao_gancho`); trocar o formato não mexe no título.
- **Bug achado nos 2 projetos reais**: legendas de narração num projeto sem narração não entravam no vídeo (o render descarta). Agora a aba avisa e “Mostrar no vídeo” passa para a origem **manual** (tempo do vídeo + deslocamento; `projeto.relogio_da_montagem`); o verificador marca como erro.
- **Legenda manual**: `POST .../legendas/cartao` (tempos do vídeo; não invade a próxima, corta no fim), `PUT .../cartao/{i}/texto` (vazio = exclui), `DELETE .../cartao/{i}`, `DELETE .../legendas`, `POST .../legendas/manual`. Toda mudança grande guarda a anterior + a origem (`legenda_origem_anterior`) e o **Desfazer** troca de volta (até a 1ª transcrição).
- **Excluir**: RASCUNHO/FINAL (`DELETE .../saidas/{arquivo}`, só nomes de saída; sem rascunho, a aprovação do rascunho cai), quadros (`DELETE .../quadros`), projeto inteiro → `projetos/_lixeira/<nome>--<data>` com Desfazer (`POST /api/lixeira/{item}/restaurar`, não sobrescreve).
- Outros: “Legenda passa do fim” virou aviso (o render já corta); erro de JS ao carregar sem projeto (`desenharMoldura`).
- Testes: `tests/test_textos_e_exclusoes.py` (5) + ajustes; suíte 190 passando. Navegador (servidor isolado): editor A × B por cliques, tocar os dois, gerar prévia, tirar título, nova legenda, editar e excluir com Desfazer, apagar RASCUNHO, excluir/restaurar projeto.
- 🟡 Não feito: arrastar a legenda para mudar a posição no vídeo; o Editor A × B não tem a grade de cenas (use os players).

🟡 Não verificado: o Command Center ainda só conhece os 4 presets embutidos (“aplique zoom X” não escolhe presets do usuário).

## 15. Revisão de PO + Tech Lead e nova rodada (17/10/2026) ✅
Base: 13 skills de social media + recomendações do agente de produção. Detalhes e backlog em `docs/PO_BACKLOG_2026-10-17.md`.
- **T1 Gravação do projeto** ✅ trava por projeto (RLock), temporário único por processo/thread, nova tentativa quando o OneDrive/antivírus segura o arquivo (`PermissionError`) e `projeto.alterar(nome, fn)`; tarefas longas (importar vídeo, momentos, transcrever, recorte IA, marca do render) gravam só o que é delas.
- **T2 `app.py` dividido** ✅ 2.327 linhas → `web/app.py` (segurança + página, 55 linhas), `web/comum.py` (utilidades) e `web/rotas/<área>.py` (APIRouter; imports explícitos gerados por AST). Mesmas 107 rotas, cada URL conferida contra a função de antes (0 diferenças). A ordem de `include_router` é a das seções originais.
- **T3 `app.js` dividido** ✅ 2.706 linhas → 17 scripts clássicos em `static/js/` (`base.js` primeiro, `inicio.js` por último; escopo global compartilhado). Teste executa todos em sequência num DOM falso e exige zero `ReferenceError`/`SyntaxError` (prova: ordem invertida falha).
- **T4 Qualidade estática** ✅ `tests/test_qualidade.py`: tudo compila, sem BOM (4 arquivos corrigidos), sem import sobrando nem `import *`, import relativo resolve até dentro de função (pegou `from ..core import timeline` quebrado na divisão), nenhuma função duplicada (Python e entre os JS), toda rota de `rotas/` registrada.
- **P2 Publicação por rede** ✅ `core/publicacao.py` + `rotas/publicacao.py` + aba 7: YouTube (título ≤ 100, ideal ≤ 70, palavra-chave nos 40 primeiros; tags ≤ 500; categoria; privacidade; **feito para crianças** e **conteúdo alterado** sempre escolhidos pelo usuário), TikTok e Instagram (≤ 5 hashtags) com “Adaptar do YouTube”, **menção tripla** da palavra-chave (falada/tela/post), hashtags genéricas, CTA genérico, crédito, ponte para o longo, **capa** (quadro do FINAL › RASCUNHO › prévia) e **PUBLICACAO.md** (também gravado ao gerar o FINAL). Projetos antigos migram sozinhos.
- **P1 Retenção medida** ✅ no verificador (nível novo “dica”): nada escrito na tela no início, fala tardia, sem legenda, planos parados acima do `max_cena` do formato (corte de cena e zoom contam como troca), planos abaixo do `min_cena` (comparação 2,2 s), duração 30–50 s, final sem loop. **Fechar o loop** (`timeline.fechar_loop`, botão ↻ e Command Center): repete 0,9 s do 1º plano no fim, fora do ranking.
- **P3 Duplicar projeto** ✅ (`POST .../duplicar` → `nome-b`, `-c`…; sem RASCUNHO/FINAL/quadros; aprovação zerada). **P4 Quadro congelado** ✅ (op `congelar`, botão ❄; render com `tpad` clone nos 4 layouts, som do jogo mudo no quadro; a prévia de dois players segura o quadro pelo relógio da página) e **versão sem áudio** ✅ (`POST .../exportar_sem_audio`, cópia da imagem sem recodificar). **P5 Corte de cena na borda do trecho** ✅ aviso. **P6 Assistir sem som** ✅ na aba 7.
- Command Center: “feche o loop”, “verifique a publicação”; corrigido “verifique …” (a regra só pegava “verific-ar”).
- Navegador (servidor isolado, porta 8767): congelar + loop + desfazer, reprodução atravessando o quadro congelado, publicação (salvar, verificar, adaptar, desfazer/refazer, exportar), duplicar e voltar, abas por clique, 320 px sem rolagem lateral, console sem erros.
- 🟡 Não feito: miniatura do vídeo longo (1280×720), teste A/B automático de títulos (é do YouTube Studio). (Testes rápidos/lentos e T5 foram feitos na §16.)

## 16. T5 funções longas + T6 testes lentos (17/10/2026) ✅
- **T5 `render.montar_comando`** ✅ 177 linhas → 27, só a sequência: `_trechos` (por trecho: `_video_do_trecho` → `_entrada_do_trecho`/`_congelar`, `_comparacao_do_trecho`, `_filtro_do_layout`; `_som_do_trecho`; concat) → `_camera_react` → `_logo_do_canal` → `_fechar_grafo` (prévia, `.ass`, quadros + `_camadas_de_audio` com `_arquivo_da_biblioteca`) → `_linha_de_comando`. Entradas e filtros num objeto `_Grafo`; validações iguais e na mesma ordem (`_conferir_fonte` para A e B).
- **T5 `legendas.gerar_ass`** ✅ 116 linhas → 26: `_visual_legenda`, `_estilo_leg`, `_cabecalho_ass`, `_eventos_gancho`, `_eventos_ranking`, `_eventos_capitulos`, `_eventos_rotulos`, `_eventos_legenda` → `_eventos_cartao` → `_texto_do_cartao`.
- **Prova de comportamento igual**: script de captura (fora do repositório) gravou ANTES da mudança 88 comandos FFmpeg + o `.ass` de cada um (15 projetos: tela_cheia, empilhado, comparação com som a/b/ambos, horizontal/longo, com e sem narração, narração desligada, deslocamento, música/efeitos/ducking, logo, ranking, capítulos, quadro congelado nos layouts, React janela+recorte IA, dividido e fundo virtual; modos proxy/rascunho/final/audio/quadros/solo/saída própria), 13 mensagens de erro e 1.009 chamadas diretas de `gerar_ass` (3 estilos × 6 layouts × visuais × ganchos × ranking/capítulos/rótulos). Depois: **idêntico byte a byte** (mesmo SHA-256 do arquivo de captura).
- **T6 ciclo rápido** ✅ `@pytest.mark.lento` em 47 funções (51 testes) que renderizam ou transcrevem; marcador registrado em `tests/conftest.py`. `python -m pytest tests -q -m "not lento"` → 173 testes em ~75 s; suíte inteira (224) 307–385 s nas duas rodadas desta mudança, continua obrigatória antes de concluir.
- 🟡 Ficaram no ciclo rápido: os testes de IA que chamam as APIs oficiais com chave falsa (~15 s, rede) e os de validação do React que só pagam a importação da câmera na fixture (~1,2 s cada). Nenhum teste barra um teste novo que renderiza sem a marca.

## 16. Revisão com ponytail + montagem automática + referências por vídeo (18/10/2026) ✅
- Revisão (`ponytail-audit` + `ui-ux-pro-max`), 4 achados corrigidos com teste: versão vertical pelo Centro de comando quebrava na 2ª vez (nome conferido como `-clipe-` e criado como `-shorts-`); a rota que salva o projeto agora lê-muda-grava sob a trava (não apaga a marca de um render que termina no meio); tarefas terminadas há mais de 1 h saem da memória; emoji dos 49 botões em `aria-hidden` (o teste de nome acessível passou a ignorar conteúdo escondido).
- `python -m clipador montar|finalizar` (`clipador/automacao.py`): do pedido ao RASCUNHO pela mesma API da tela (trechos explícitos, pedido pela fala ou melhor momento; foco automático na tela cheia; prévia para gravar a narração). `finalizar` = legendas da narração + RASCUNHO novo. Nunca gera FINAL e nunca escreve texto.
- `referencias/videos/<nome>/` + `python -m clipador referencia NOME`: perfil medido de vídeos locais (duração, plano médio, fala) que `montar --referencia` aplica (duração-alvo e duração do momento).
- Testes: `tests/test_automacao.py` (5, lentos; fala real pela voz pt-BR do Windows).
- 📋 Remotion (skill instalada): fica para títulos/gráficos animados renderizados à parte e sobrepostos pelo FFmpeg; não substitui o render atual.

## 6. Como executar e validar
```bash
python -m clipador          # abre http://127.0.0.1:8765 (ou "Abrir Clipador.bat")
python -m pytest tests -q   # 224 testes, ~300–390 s (os de IA marcados como REAL ou SIMULADO em tests/test_ia.py)
python -m pytest tests -q -m "not lento"   # ciclo rápido: 173 testes, ~75 s (sem render nem transcrição)
```
Validação manual sugerida: criar "+ Novo" em Vídeos curtos → Compilado; adicionar o trailer; 5 trechos com rótulo;
aba 4 · Áudio: colocar uma música em `musicas/`, ajustar volume, ouvir solo e mixagem; aba 7: gerar quadros e rascunho.



