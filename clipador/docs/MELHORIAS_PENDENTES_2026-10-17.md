# Melhorias pendentes — anotadas em 17/10/2026 (para executar com outro agente)

Origem: produção dos 10 Shorts inspirados em referências virais (`projetos/v01…v10`, script de montagem em
`projetos/_fontes_inspiracoes/montar.py`). Nada abaixo foi implementado ainda. Rode `python -m pytest tests -q`
antes e depois de cada item.

## 1. Vídeo comentado (caso "Olha o que a Eleven disse sobre GTA 6")
O que JÁ existe e foi usado no `v10-eleven-gta6`:
- Gancho (título do início) com `ate` = duração da introdução.
- Som original mudo/volume POR TRECHO (`segmento.audio = {"modo": "mudo"|"volume"|"padrao", "db"}`).
- Narração com `deslocamento` e ducking da trilha original.

O que FALTA (recomendado, prioridade alta):
- **Trecho "quadro congelado" na timeline** (op `congelar` em `core/timeline.py`: N segundos do quadro escolhido,
  com desfoque/escurecimento opcional). Hoje foi feito à mão: PNG + FFmpeg → `eleven_intro_3s.mp4` como fonte extra.
- **Preset de formato "comentado"** em `core/formatos.py`: cria intro de 2–3 s (congelado), gancho editável,
  original mudo na intro e som original 100 % depois, narração só na intro, ducking desligado no resto.
- **Gravar narração só de um intervalo** (aba 5): hoje a gravação cobre a prévia inteira; permitir gravar
  apenas 0–3 s com teleprompter curto.

## 2. Tradução de legendas de vídeos virais (caso "Lucia POV", `v05`)
- Não existe tarefa de tradução. Sugestão: tarefa de IA `traduzir` em `core/ia/assistente.py` (só texto,
  com prévia e consentimento, como as outras) que traduz os cartões de `transcricao.json` da fonte mantendo
  os tempos; fallback local manual (editar cartão a cartão, já existe).
- **Cobrir texto queimado do original**: faixa/caixa (cor ou desfoque) sobre uma região escolhida na prévia,
  para esconder o texto em inglês antes de pôr o português. No v05 o gancho em PT ficou por cima do texto original.
- Botão "Traduzir vídeo" que encadeia: baixar link → transcrever fonte (já existe) → traduzir → legenda origem `video`.

## 3. Exportar sem áudio
- Pedido recorrente: o usuário põe a música pelo próprio YouTube. Falta opção "Exportar sem áudio" no render
  (`-an`, pular loudness/2ª passada → render mais rápido). Hoje foi feito depois com `ffmpeg -an -c:v copy`.

## 4. Comparações e "versões" de um mesmo clipe
- `v08` (PS1→PS5): as versões degradadas foram geradas fora do app (FFmpeg: escala baixa + posterização etc.).
  Sugestão: efeito por trecho `retro` com presets PS1/PS2/PS3/PS4.
- `v01`/`v07`: a comparação A×B exige escolher manualmente o trecho do B; um "parear cenas parecidas"
  (por cor/movimento, sinais que `destaques.py` já calcula) economizaria muito tempo.
- Rótulo por trecho em tela cheia (ex.: "BARCO 2013") hoje é feito com cartão de legenda manual; um campo
  `rotulo` visível no layout tela_cheia seria mais limpo (o campo já existe para ranking/capítulos).

## 5. Outras funcionalidades úteis
- **Emoji na legenda**: Arial Black não desenha emoji (as referências usam 😭💀). Adicionar fonte de fallback
  (Segoe UI Emoji) no .ass ou trocar emoji por imagem.
- **Projeto em lote a partir de lista de links de referência**: criar N projetos com formato sugerido
  (`referencias.py` já mede duração/cortes).
- **Duplicar projeto** (para variações A/B de gancho) — hoje só dá para duplicar kit.
- **Pasta de saída configurável** ("videos prontos") com cópia automática ao gerar.
- Biblioteca de "momentos" do trailer com tags (dança, carro, praia, pôr do sol…) para reaproveitar entre projetos.

## 6. Dicas de otimização de tempo
- Montar por script usando `fastapi.testclient` contra `clipador.web.app` (sem abrir navegador) — 10 projetos
  em poucos minutos; ver `montar.py`.
- Ter um tile de miniaturas com tempo (1 quadro/s) de cada fonte em cache: escolher trechos ficou 10× mais rápido.
  Sugestão: rota `GET .../fontes/{fid}/mosaico`.
- Cache de cenas/tarjas por arquivo (hash) compartilhado entre projetos: hoje cada projeto reanalisa o trailer.
- Renderizar vários rascunhos em fila em paralelo limitado (2 por vez) quando a CPU permite.

## 7. Bugs encontrados durante a produção
- **OneDrive trava `projeto.json`**: `projeto.salvar` deu `PermissionError [WinError 5]` no `os.replace` quando
  houve vários salvamentos seguidos (legenda manual em sequência). Pôr nova tentativa com espera curta (3× 0,2 s)
  em `core/projeto.py:salvar`, ou mover `projetos/` para fora do OneDrive.
- Trechos que cruzam um corte de cena pegam um pedaço da cena seguinte (ex.: v07 "PÔR DO SOL 2026" mostra o logo
  e depois a Lucia). Seria útil um alerta "este trecho atravessa um corte de cena" usando `fonte.cenas`.

## 8. Lote 2 — formatos de Shorts com 1M+ views (17/10/2026)
- Script: `projetos/_fontes_inspiracoes/montar_lote2.py` (n01 humor "parece GTA 5", n02 humor "2 bilhões",
  n04 GTA 5 do PS1 ao PS5, n05 comentado Trevor). Fontes de referência: canal Abhi__69 (humor rápido, dezenas de
  Shorts de 1M–24M), Fxy (comentado com celebridade/ator), POWER PLAY EXE (PS1→PS5).
- **Falta material de gameplay**: os formatos "Rockstar achou que ninguém ia perceber" (2,4M), "GTA 5 fez isso
  MELHOR" (5,5M) e "Yeah gotta wait for GTA 7" precisam de gameplay/cenas longas que os trailers não têm.
  Sugestão: biblioteca `fontes/gameplay/` com clipes gravados pelo usuário (GTA 5 PC/console) para destravar esses formatos.
- **Busca de referências virais**: um botão "achar Shorts 1M+ de um canal" (yt-dlp `--flat-playlist` na aba
  /shorts, filtrando views e título) poupa tempo; hoje foi feito à mão no terminal.
- Recurso pedido pelos formatos de humor: **círculo/seta de destaque** (anotação sobre o vídeo) e
  **inserção de meme/reação** (imagem ou clipe curto no meio).

## 9. Recomendações novas (após as skills de Shorts, lote 3)
Prioridade alta (cada uma economiza passos manuais que repeti nos 3 lotes):
1. **Botão "fechar o loop"**: acrescenta no fim o primeiro plano (0,9 s) e estende a última legenda. Fiz à mão em v02/v03/v09.
2. **Ficha de publicação por projeto** (título com palavra-chave, descrição, hashtags até 5 no Instagram) com checagem:
   título ≤ 70 caracteres, aviso se o título promete algo que não está nas fontes (ex.: "trailer 3"). O campo
   `publicacao` existe, mas não há validação nem exportação em lote (`PUBLICACAO.md`).
3. **Formatos prontos no `core/formatos.py`**: `humor_rapido` (título-piada 3–5 s + 2 legendas curtas, final com folga p/ narrar),
   `comparacao_ab` (pares de cenas), `ps1_ao_ps5` (efeito retrô por geração), `contagem` (X dias para…), `lista_numerada`.
4. **Efeito retrô por trecho** (PS1/PS2/PS3/PS4): hoje feito com FFmpeg fora do app (`lutrgb` + escala baixa).
5. **Salvar com nova tentativa** (OneDrive trava `projeto.json`): ver seção 7.
6. **Aviso de corte de cena dentro do trecho** (seção 7) — repetiu em v07/n01.
7. **Biblioteca de gameplay do usuário** (seção 8) para os formatos que o trailer não cobre.

8. **Preset "Comparação de gerações" (PS1→PS5)**: um clique cria a tela dividida PS1…PS4 × PS5 com efeito retrô
   e legenda "PSx × PS5", 2,4 s por par (regra do usuário: comparar = tela dividida, nunca troca rápida).
9. **Rótulo A/B por trecho** na comparação (hoje `rotulo_a/b` é do projeto inteiro; usei legenda como rótulo).
10. **Validar antes de renderizar**: legenda além do fim do vídeo, trecho que pega cartão "Rockstar Presents"/logo
    final (detectar quadro quase todo escuro/texto central), planos < 2 s em vídeos de comparação.
11. Mostrar no app a **duração mínima recomendada por plano** conforme o formato (comparação ≥ 2,4 s; humor: título 3–5 s).

Prioridade média:
- Montar vários projetos por **script/lote** com a mesma API (já funciona via `TestClient`); expor como `python -m clipador lote arquivo.json`.
- **Mosaico de miniaturas com tempo** por fonte (`GET .../fontes/{fid}/mosaico`) — foi o que mais acelerou a escolha de trechos.
- **Renderizar em fila** com 2 jobs em paralelo; hoje cada rascunho espera o anterior (lote de 10 leva vários minutos).
- **Painel de cobertura de texto queimado** (v05): retângulo sólido/desfoque sobre região escolhida, com cor amostrada do original.
- Exportar `PUBLICACAO.md` + miniaturas de capa (primeiro quadro bom) ao copiar para "videos prontos".

Skills instaladas (16, do repositório social-media-skills/skills, copiadas de zip revisado): youtube-shorts,
short-form-video-script, reels-script, tiktok-script, hook-writer, viral-reverse-engineering, meme-and-culture, trend-jacking,
captions-and-clipping, caption-writer, platform-specs-and-validation, youtube-publishing-and-metadata, hashtag-strategy,
thumbnail-design, cross-platform-repurposing, content-recycling. Pendente: ffmpeg-llm (rendi-api/ffmpeg-llm).

## 10. Observações
- O trailer não tem cachorro: o `v07` adaptou o formato "Chop 2013 × 2026" para barco/pôr do sol.
- `v09` fala de um RUMOR (conta de hospital); o texto deixa claro "ainda não é oficial".
- `v05` e `v10` usam vídeos de outros canais como fonte — atenção a direitos/crédito ao publicar.

- ffmpeg-llm (rendi-api/ffmpeg-llm, v0.1.0, autor Yuval Yakubov) instalado em 18/10/2026: skill ffmpeg-command, comando /ffmpeg e agente ffmpeg-expert em ~/.claude. Hooks vazios, só texto.

- Remotion (remotion-dev/skills, oficial) instalado em 18/10/2026: remotion-best-practices, -create, -captions, -render, -multimedia, -docs (sem mapas/SaaS/upgrade/markup). Remotion = vídeo por código (React/Node); licença exige conferir se o uso é comercial (remotion.dev/license).
