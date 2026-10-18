# CLAUDE.md - Diretrizes do Projeto GTA 6 Shorts Viral

Este repositório contém a pipeline completa de produção de vídeos curtos (YouTube Shorts, TikTok, Instagram Reels) para análise do trailer oficial de GTA 6, sincronizado com narração do usuário gravada em estúdio desktop próprio.

---

## 🚨 REGRAS CRÍTICAS E OBRIGATÓRIAS (NUNCA VIOLE)

1. **JAMAIS DECLARAR O VÍDEO COMO "PRONTO" OU "FINAL" PREMATURAMENTE:**
   - Toda renderização gerada é estritamente um `RASCUNHO` para avaliação do usuário.
   - Sempre gere quadros de revisão (PNG) ou vídeo `RASCUNHO_*.mp4` e peça a revisão e aprovação explícita do usuário antes de qualquer export definitivo.

2. **PADRÃO DE LEGENDAS (SHORTS VIRAIS / RETENÇÃO):**
   - **Segmentação por pausas naturais:** Use `faster-whisper` com quebra em pausas/silêncios ($\ge 0.35$s), no máximo 5 palavras por cartão e no máximo 34 caracteres.
   - **Proibido fatiamento arbitrário:** NUNCA fatie arbitrariamente palavras ou force duração mínima artificial (ex: 0.6s), pois isso faz a próxima frase vazar na tela antes do tempo.
   - **Estilo Visual:** Formato ASS com efeito karaokê real (`\k` com destaque em amarelo `#FFDE00`, texto base branco `#FFFFFF`, fonte `Arial Black` tamanho 88, contorno preto espesso 7px, sombra 2px).
   - **Zona Segura (Safe Zone):** Posição vertical $y=1330$ (área segura do YouTube Shorts: livre de botões laterais de like/comentário e do rodapé com nome do canal/som).
   - **Zero sobreposição:** Intervalos de tempo estritamente sequenciais.

3. **ENQUADRAMENTO VISUAL (1080x1920):**
   - **Fonte original:** Sempre use o trailer 1080p autêntico (`gta6_launch_trailer_1080p.mp4`).
   - **Remoção de tarjas:** Remova as tarjas pretas cinematográficas nativas (`crop=1920:960:0:60`).
   - **Layout Empilhado (Stacked Layout):** O bloco nítido de ação ocupa $1080 \times 864$ posicionado em $y=300$ (abaixo dos botões superiores), com fundo desfocado e escurecido preenchendo as bordas superior/inferior. NUNCA use efeito simples de blur esticado centralizado de baixa resolução.

4. **CADEIA DE TRATAMENTO DE ÁUDIO (FFmpeg DSP):**
   - **Voz do usuário:**
     - Highpass em 90 Hz (remove rumble e vento).
     - Redução espectral de ruído (`afftdn=nf=-28`).
     - Equalizador corretivo: atenuação em 300 Hz (-2 dB, remove efeito abafado/caixa) + presença em 3000 Hz (+4 dB) + brilho em 6500 Hz (+2 dB).
     - De-esser (`deesser=i=0.2`), compressor suave e limitador (`alimiter=limit=0.89`).
   - **Mixagem com a trilha do trailer:**
     - Trilha atenuada para ~ -20 dB.
     - *Sidechain compression ducking* automático (`sidechaincompress`): a trilha sonora do trailer baixa automaticamente sempre que a voz do usuário entra.
     - Normalização final EBU R128 (`loudnorm=I=-14:TP=-1:LRA=9`).

5. **GRAVAÇÃO DA NARRAÇÃO (aba 5 do Clipador):**
   - Grava no navegador sobre a prévia da montagem (proxy.mp4), com teleprompter rolando junto, medidor de nível, contagem 3-2-1 e vídeo+voz começando juntos.
   - Nada é salvo sozinho: o usuário ouve a gravação e confirma em "Salvar narração". Sem processamento do navegador (eco/ruído/ganho automático desligados); o tratamento é a cadeia da regra 4.

---

## 🛠️ COMANDOS E FLUXO DE EXECUÇÃO

### Clipador (software principal, desde 16/10/2026)
Site local que substituiu todas as ferramentas antigas.
```bash
python -m clipador            # abre http://127.0.0.1:8765  (ou duplo clique em "Abrir Clipador.bat")
python -m pytest tests -q     # 233 testes (~6–13 min). OBRIGATÓRIA antes e depois de qualquer mudança e antes de concluir.
python -m clipador montar NOME --fonte VIDEO [--formato X] [--layout Y] [--trechos 14-20,31-36 | --pedido "fala"] [--referencia ID]
python -m clipador finalizar NOME [--narracao voz.wav]    # legendas da narração + RASCUNHO novo (FINAL nunca)
python -m clipador referencia NOME   # mede os vídeos de referencias/videos/NOME/ e cria o perfil
python -m clipador canal|ideia|roteiro|esteira|metricas|experimento|custo ...   # estúdio CPV (docs/cpv/10-manual-operacional.md)
python -m pytest tests -q -m "not lento"   # ciclo rápido enquanto edita: 173 testes (~75 s), sem render nem transcrição
```
- **Fluxo do usuário (18/10/2026):** ele pede o vídeo na conversa; o Claude monta com `clipador/automacao.py` (mesma API da tela, em processo) até o RASCUNHO sem narração; o usuário grava a narração na aba 5 (ou manda o arquivo) e o Claude roda `finalizar`. O app na tela é para ajustes. O agente não escreve título nem legenda à mão; FINAL só com aprovação no app.
- **Estúdio CPV (docs/cpv):** canais (`core/canais.py`; 4 sementes: Mapa Esquisito, História Esquisita, Como o Espaço Funciona, GTA 6 Comparado com monetização `sem_receita`), ideias com portões + pontuação 0–100 de pesos fixos (`core/ideias.py`; priorização, não probabilidade), roteiros por formato com fontes por afirmação e aprovação do USUÁRIO (`core/roteiros.py`; sugestão da IA só entra com aplicar), originalidade no canal, conformidade (`core/conformidade.py`, regras F1–F11 da matriz 04), registro de direitos (`core/recursos.py`), esteira de 12 etapas deduzidas do estado real (`core/esteira.py`; publicação só registrada pelo usuário), métricas pelo CSV do Studio, experimentos (inconclusivo com amostra pequena) e finanças (observado × projeção do usuário). Canais em português, narração do usuário.
- **GTA 6 / Take-Two:** a política oficial só tolera uso NÃO comercial; não monetizar material de GTA sem licença escrita (canal 4).
- Referências por vídeo: o usuário solta vídeos em `referencias/videos/<nome>/`; `referencias.analisar_videos` mede duração, plano médio (cortes do FFmpeg) e ritmo de fala (Whisper, texto descartado) e grava o perfil em `referencias/<nome>.json` (mesmo formato dos perfis de canal: comparar/aplicar). Layout e estilo de legenda: o Claude olha quadros dos vídeos e propõe; não são medidos.
- Testes lentos: todo teste que renderiza (render/quadros/prévia/exportar, câmera do React) ou transcreve leva `@pytest.mark.lento` (marcador registrado em `tests/conftest.py`). Teste novo que renderiza também leva. O ciclo rápido não substitui a suíte inteira.
- Código: `clipador/core/` (núcleo sem interface: projeto, midia, destaques, legendas, layouts, audio, formatos, render, tarefas, publicacao, timeline…) e `clipador/web/`: `app.py` (só segurança, página e ordem dos roteadores), `comum.py` (utilidades/validações das rotas), `rotas/<área>.py` (um APIRouter por área, imports explícitos; a ordem de `include_router` importa) e `static/` (`index.html` + `js/*.js`: scripts clássicos por aba, `base.js` primeiro e `inicio.js` por último — função usada ao carregar tem de estar num arquivo anterior). Não existe mais `app.js`.
- Gravar projeto: `projeto.salvar` tem trava por projeto e nova tentativa (OneDrive); tarefa em segundo plano usa `projeto.alterar(nome, fn)` para gravar só o que é dela. `tests/test_qualidade.py` barra BOM, import sobrando/quebrado (inclusive dentro de função), função duplicada e rota fora do app.
- Publicação (`core/publicacao.py`, aba 7): campos por rede (YouTube/TikTok/Instagram), limites, menção tripla da palavra-chave, capa (`capa.png`) e `PUBLICACAO.md` (também ao gerar o FINAL). “Feito para crianças” e “conteúdo alterado” são declarações do usuário: o app nunca escolhe, só cobra. Sem previsão de views.
- Retenção no verificador (nível `dica` além de erro/aviso): gancho escrito, planos vs `max_cena`/`min_cena` do formato, legenda, duração, loop, corte de cena na borda do trecho. Timeline: `fechar_loop` (trecho `loop`, fora do ranking) e `congelar` (trecho `congelado`: 1º quadro parado com `tpad`, som do jogo mudo; `fim - ini` é só a duração). Duplicar projeto (`nome-b`), versão sem áudio (`_sem_audio.mp4`) e “Assistir sem som” na aba 7.
- Status, riscos e plano por fases: `clipador/docs/AUDITORIA.md` (atualize os estados ✅/🟡/📋 ao concluir algo).
- Duas áreas: **curto** (9:16) e **longo** (16:9 1920×1080, sempre layout `horizontal`, com capítulos). Formatos com preset + guia: guias, noticias, gameplay, curiosidades, compilados (`core/formatos.py`, pesquisa em `docs/FORMATOS_VIRAIS.md`). Ranking 1…N (compilados) e capítulos usam o campo `rotulo` de cada trecho.
- Segurança (não remover): middleware em `web/app.py` só aceita Host local e recusa comandos de outros sites; toda entrada que vira parâmetro do FFmpeg é validada (`app.py`, `audio.validar`, `projeto.CROP_RE`).
- **Git (desde 18/10/2026):** repositório nesta pasta, identidade genérica `Clipador <clipador@localhost>` (nunca o e-mail da conta), `main` = estado inicial e trabalho em ramos (`cpv-implementacao`); 1 commit por item, sem push. Antes de cada commit: varrer por e-mail, caminho pessoal (C:\Users\...) e chaves. Fora do Git (.gitignore): projetos/, estudio/, vídeos/áudios, _versoes/, config/, kits/, modelos/, `.claude/launch.json`. Zips em `_versoes/` continuam como backup extra.
- IA (`core/ia/`): Claude pelo SDK oficial `anthropic` (padrão `claude-opus-5-5`, fallback `"default"`), OpenAI e Gemini pelos SDKs deles, Ollama local. Chaves SÓ no cofre do Windows (`keyring`, serviço `Clipador-IA`; testes usam `Clipador-IA-TESTES`) ou variável de ambiente — nunca em arquivo, log, resposta da API ou navegador. Config sem segredos em `config/ia.json`; histórico em `config/ia_historico.jsonl` (só metadados por padrão). Só texto é enviado, com consentimento por provedor; nada é aplicado ao projeto sem clique. Não fixe nomes de modelos de OpenAI/Gemini no código (a lista vem da conta).
- React (aba 9, `core/react.py`): câmera em `projetos/<n>/react/camera.mp4` (+ `matte.mp4` do recorte por IA, modelo MediaPipe em `modelos/`), modo janela/dividido/fundo_virtual, chroma key FFmpeg; o microfone da gravação vira `narracao.wav`. A câmera é atrasada com `tpad` (não use `-itsoffset`: o `setpts` zera). Recorte por IA roda local; não prometa remoção perfeita.
- Skills de terceiros instaladas em `.claude/skills` (jakubkrehel/skills, obra/superpowers sem hooks, morluto/rea só `reverse-engineer-anything`; DietrichGebert/ponytail só as 6 skills, sem hooks/band; nextlevelbuilder/ui-ux-pro-max só `ui-ux-pro-max`; multica-ai `karpathy-guidelines` — origem e SHA-256 em `ORIGEM.txt` de cada pasta); Node.js 24 LTS instalado; REA registrado no Claude Code (`~/.claude.json`, backup `.rea.backup`) — serve para binários/apps locais, não para ver o servidor de sites.
- Legendas: presets por plataforma em `legendas.PLATAFORMAS` (recomendações, não regras oficiais), visual em `projeto.legenda` (fonte/tamanho/contorno/sombra/cor/destaque/animacao, validados em `app._validar_legenda`), tempo por palavra `PUT .../legendas/cartao/{i}`, SRT `GET .../legendas.srt`. Regra 2 (karaokê amarelo y=1330) = preset Shorts.
- Momentos (aba Cortes, `core/destaques.py`): sinais locais em cache + `momentos()` com motivos; rotas `.../fontes/{fid}/destaques` (analisar, `/aplicar`, `/lote`) e `POST .../foco_auto`. Nota é relativa ao vídeo, não previsão de views.
- Pedido (`core/pedido.py`): transcrição da FONTE em `cache/<fonte>/transcricao.json` (idioma automático), busca local `POST .../pedido` (modo local|ia; IA só texto, com `/pedido/previa`), `GET .../transcricao_timeline` + op `cortar_intervalo` para editar pelo texto.
- Kit do canal (`core/kits.py`): `kits/<id>.json` + logos em `kits/logos/`; `projeto.marca` desenhada no render (área segura, sob a legenda). Biblioteca de estilos (janela `#dlg-kits`, funciona sem projeto): kit em branco, duplicar, renomear (troca o arquivo; nome repetido = 409), editar via `PUT /api/kits/{id}` validado em `app._validar_kit`; `kit.zoom_padrao` aplicado só aos trechos sem zoom por `POST .../kit/zoom` (a interface desfaz). Presets de zoom do usuário em `kits/zoom/presets.json` (`zoom.todos()`; embutidos fixos; excluído vira "personalizado" com os mesmos valores). Não coloque outros .json soltos em `kits/` (cada um é um kit). Versão 1:1: `render.exportar_1x1` recorta RASCUNHO/FINAL prontos (comparação e React dividido não têm 1:1).
- Prévia da timeline (aba Cortes): dois players alternados (#player-fonte/-b), corte por quadro (igiarTL), nunca por 	imeupdate (ver AUDITORIA.md §9). O servidor manda Cache-Control: no-cache nos estáticos.
- Zoom (core/zoom.py): segmento.zoom_fx = preset (destaque/impacto/reacao/lento) + intensidade, inicio, duracao, curva, volta, ponto foco_x/foco_y; render com `perspective` subpixel (NUNCA scale+crop com tamanho par: tremia). Zoom antigo (`zoom` numérico) vira `lento`. Prévia exata: `POST .../previa_trecho`; picos: `POST .../zoom/sugerir`.
- Command Center (core/comandos.py): `/comando/interpretar` (regras PT; IA opcional só escolhe ações do catálogo) e `/comando/executar` (valida e chama funções do app). Nada executa sem o clique em Executar.
- Verificador (core/verificador.py, `GET .../verificar`) e assistente de ritmo (`GET .../ritmo`). Legendas: `legenda_origem` = narracao | video; `*palavra*` = destaque; `.vtt`. Prévia: `proxy_hash`/`proxy_atual`; o render só grava a sua marca (recarrega o projeto). React: `recorte` (posição do fundo virtual), `recorte_ia` com limiar/borda/estabilidade (filtro guiado).
- Timeline (aba Cortes): operações em `core/timeline.py` via `POST /api/projetos/{n}/timeline` (dividir, duplicar, mover, aparar com ímã, remover); a interface só chama essa rota.
- Referências (`core/referencias.py`, perfis em `referencias/`): medem técnica (duração, fala, cortes, títulos, capítulos); legenda baixada só para contar palavras e descartada. Perfil real: `[terceiro]-gta-6`.
- Projetos: `projetos/<nome>/projeto.json` (+ narracao.wav, legenda_cartoes.json, legenda.ass, quadros/, RASCUNHO_*.mp4, FINAL_*.mp4).
- Aba 6 · Textos (era Legendas): título do início, rótulos A/B, legendas e visual; tudo editável clicando sobre a prévia (`#tx-editor`). `legenda_origem` = narracao | video | manual (manual e video = tempo do vídeo, sempre visíveis; `projeto.relogio_da_montagem`). Legenda manual: `POST/PUT/DELETE .../legendas/cartao…`, `DELETE .../legendas`, `POST .../legendas/manual`; Desfazer = `/legendas/restaurar` (troca cartões e origem). O formato só SUGERE o gancho (`guia.sugestao_gancho`), nunca escreve texto sozinho.
- Excluir: `DELETE .../saidas/{arquivo}` (RASCUNHO/FINAL), `DELETE .../quadros`, `DELETE /api/projetos/{n}` → `projetos/_lixeira/` + `POST /api/lixeira/{item}/restaurar`. Editor A × B na aba Cortes (dois players, mesma duração).
- Fluxo da interface: Fonte → Cortes → Estilo → Áudio → Narração (grava no navegador sobre `proxy.mp4`, sincronizado) → Textos → Revisar (quadros → RASCUNHO → Aprovar → FINAL). O FINAL é bloqueado no servidor se o conteúdo mudou depois da aprovação (hash em `projeto.json → aprovacao`).
- Interface (revisada em 16/10/2026, ver AUDITORIA.md §8): 7 etapas numeradas + Extras (Assistente, React); faixa "Próximo passo"; Estilo e todo o resto salvam na hora; ações reversíveis usam aviso com Desfazer (não confirm); atalhos de uma tecla só com o foco na timeline; microfone só em "Ativar microfone". Todo controle novo precisa de nome acessível e texto >= 12 px — 	ests/test_interface.py guarda isso.
- Layouts: `empilhado` (regra 3, padrão do projeto GTA 6), `tela_cheia` (recorte 9:16 + zoom), `comparacao` (A×B: dois vídeos, A em cima e B embaixo; formato "comparacao" só no curto; `projeto.comparacao` = fonte_a/fonte_b/rótulos/som a|b|ambos/divisória, cartão na aba Fonte, `POST .../comparacao/montar`; não é React). Outros layouts que não o empilhado só com escolha explícita do usuário.
- Estilos de legenda: `karaoke` (regra 2), `palavra` (1–3 palavras no centro), `caixa` ([terceiro]). Cartões nunca terminam em artigo/preposição se couber no próximo; sem duração mínima artificial. Legenda nunca passa do fim do vídeo (`legendas.limitar` na geração, .ass e SRT); `legenda_base` detecta legenda desatualizada → botão "🔄 Atualizar legendas" (anterior em `legenda_cartoes.anterior.json`, Desfazer via `/legendas/restaurar`).
- Áudio (aba 4) = 4 trilhas independentes, modelo v2 em `core/audio.py` (projetos antigos migram sozinhos): **original** (volume com/sem narração + volume/mudo por trecho em `segmento.audio`), **música** (`musicas/`), **narração** (deslocamento; a legenda acompanha o deslocamento na geração do .ass), **efeitos** (`efeitos/`), **mix** (ducking leve/média/forte, normalização). Bibliotecas: o usuário coloca os arquivos ou baixa o áudio de um link — o Claude não baixa música protegida por conta própria. Toda camada termina com `apad=whole_dur` + `atrim` (sem isso o FFmpeg estoura memória quando uma trilha acaba antes). Prévia "solo" por trilha sem normalização. 2ª passada de loudness (`render.ajustar_loudness`) porque o loudnorm de uma passada erra 1–2 dB em vídeos curtos.
- Render: grava em `.tmp`, verifica com ffprobe (duração, trilhas, resolução) e só então renomeia; tarefas canceláveis (`POST /api/tarefas/{id}/cancelar`).
- `render.montar_comando` é só a sequência `_trechos` (vídeo/som por trecho, congelado, A×B) → `_camera_react` → `_logo_do_canal` → `_fechar_grafo` (prévia/.ass/quadros + `_camadas_de_audio`) → `_linha_de_comando`; a ordem das entradas `-i` faz parte do comando. `legendas.gerar_ass` = cabeçalho + `_eventos_gancho/_ranking/_capitulos/_rotulos/_legenda`. Ao mexer neles, compare o comando/.ass gerado antes e depois (deve sair idêntico se a intenção não é mudar o vídeo).
- Docs: `clipador/docs/ARQUITETURA.md`, `AUDITORIA.md`, `PESQUISA_SHORTS.md`, `FORMATOS_VIRAIS.md`.
- Projeto migrado: `projetos/gta6-launch-trailer` (trailer 14–63,5 s, empilhado, narração e legendas antigas).
- Render com vigia: FFmpeg 3 min sem avançar é encerrado (`render.executar`).
- Bug conhecido do FFmpeg 9: não usar `zoompan` (gera quadros a mais e desalinha a montagem); o zoom lento é `scale` com `eval=frame` em `layouts.tela_cheia`.

O código antigo do Antigravity (montar_short.py, gravador_desktop.py, extensão do Chrome, vídeos de teste e rascunhos antigos) está em `_arquivo_antigravity/` apenas como arquivo morto: não usar nem manter. Pode ser excluído quando o usuário quiser.

---

## 📂 ESTRUTURA DOS ARQUIVOS

- `gta6_launch_trailer_1080p.mp4`: trailer 1080p 30 fps (com tarjas, crop=1920:960:0:60).
- `minha_narracao_gta6.wav`: narração antiga do usuário (usada em `projetos/gta6-launch-trailer`).
- `clipador/`: o software. `projetos/`: um projeto por pasta. `Abrir Clipador.bat`: atalho. `tests/`: testes.
- `musicas/`, `efeitos/`: bibliotecas de áudio do usuário (compartilhadas entre projetos).
- `_versoes/`: zips de segurança extras (o controle de versão principal agora é o Git).
- `estudio/`: dados do estúdio (canais, ideias, roteiros, métricas, experimentos, custos) — do usuário, fora do Git.
- `clipador/docs/cpv/`: pesquisa e estratégia CPV (01–10) + rascunho do e-mail à Take-Two.
- `projetos/gta6-antes-do-logo`: Short novo (20 s, tela cheia, legenda palavra) com legenda PROVISÓRIA até o usuário gravar a voz.
- `_arquivo_antigravity/`: lixo arquivado.

---

## 💡 HISTÓRICO DE ERROS E COMO FORAM RESOLVIDOS

| Erro Anterior | Causa Raiz | Como o Claude Resolve |
| :--- | :--- | :--- |
| **Legendas partidas / descompassadas** | Chunking fixo de 3 palavras com durações mínimas forçadas (0.6s) | Faster-Whisper com corte em pausas ($\ge 0.35$s), máx 5 palavras, formato ASS com tags `\k` |
| **Imagem borrada e centralizada** | Download de 360p com tarjas pretas nativas e filtro boxblur simples | Download 1080p via Deno/yt-dlp, remoção de tarjas com `crop` e empilhamento em bloco nítido |
| **Voz abafada** | Microfone sem fio com perda de altas frequências | EQ cirúrgico (corte em 300Hz, ganho em 3kHz e 6.5kHz) + de-esser + sidechain ducking |
| **Interface do gravador travando** | `_tick` a 15ms tentando decodificar 1080p ocupando 100% da CPU | `_tick` a 33ms (30 FPS), pulo de frames com `cap.set`, resize linear e feedback assíncrono |
| **Erro de sintaxe no app HTML** | Template string quebrada `${mins}:;` no JavaScript | Corrigido para `mins + ':' + secs`, testado e validado via Deno |
| **Duração mínima de 0.5 s ainda no código** | o `montar_short.py` antigo mantinha `duracao_minima` contra a regra 2 | Removida no Clipador; fim do cartão = última palavra + 0.12 s, sempre antes do próximo |
| **Narração não casava com a imagem; loudness −15,4 LUFS** | Um único segmento de 49 s sob um roteiro de 4 assuntos; loudnorm de 1 passada | Timeline por segmentos + gravação sobre a prévia; 2ª passada de loudness (−14,2 LUFS medido) |






