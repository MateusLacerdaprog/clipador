# Formatos que viralizam — Guias, Notícias, Gameplay, Curiosidades, Compilados

Pesquisa de 16/10/2026. Dados **observados** (metadados públicos via yt-dlp + busca do YouTube com
filtro Shorts, sem baixar vídeos) separados das **recomendações** (minha interpretação). Amostra: 100
Shorts reais (20 por categoria, PT+EN, nicho GTA) e os 6 vídeos longos mais vistos de cada categoria
(com capítulos). Views/inscrito = quantas vezes o vídeo superou o tamanho do canal (alcance fora da base).
Títulos, canais e links dos vídeos medidos são de terceiros e ficam só na máquina, fora do Git.

## Resumo numérico (observado)

| Categoria | Shorts: duração mediana (p25–p75) | Shorts: views ÷ inscritos (mediana) | Longos: duração mediana (top 20) |
|---|---|---|---|
| Guias | 24,5 s (19–39) | 8,1× | 11,6 min |
| Notícias | 29 s (21–43) | 4,2× | 20,8 min |
| Gameplay | 16,5 s (13–29) | **26,6×** | 58,7 min (séries com mais de 140 episódios) |
| Curiosidades | 34 s (24–56) | 2,4× | 26,3 min |
| Compilados | 21 s (13–33) | **20,1×** | 11,2 min |

Gameplay e Compilados são os que mais "furam a bolha" (canais pequenos com milhões de views).

## 1. Guias / Dicas
**Observado**
- Truque de GTA Online — 10,8 mi, 24 s. Tela cheia vertical, legenda de 1–2 palavras no centro, título no topo nos
  2 primeiros segundos, **ícone do botão do controle com seta vermelha** mostrando o que apertar, sticker de meme.
- Dinheiro para iniciante — 4,6 mi com 10,6 mil inscritos, 11 s.
- Dicas para iniciante — 5,3 mi, 34 s, dentro de uma série numerada ("Parte 5").
- Longos: capítulos por etapa (um negócio por capítulo), 10–16 min; lista "o que fazer primeiro" em 3 min.

**Recomendação de formato**
- Curto: 1 truque = 1 vídeo (11–35 s). Gancho = resultado ("dinheiro infinito", "truque secreto"),
  depois **o passo a passo mostrando o botão**, prova do resultado no fim. Série numerada.
- Longo: intro de 20–40 s dizendo o que a pessoa vai conseguir → capítulos por etapa → resumo.

## 2. Notícias
**Observado**
- Vazamento de GTA 6 — 7,8 mi com 2,6 mil inscritos, **8 s**: moldura temática (arte de fundo + logo),
  selo fixo de "vazado", vídeo empilhado no meio, sem narração.
- Os mais recentes (out/2026) têm 7–30 s, um fato por vídeo, títulos curtos em caixa alta.
- Longos: análise com capítulos temáticos (15–41 min) publicados 1–3 dias depois do anúncio (Aug/2026).

**Recomendação**: velocidade > produção. Selo fixo ("NOTÍCIA", "OFICIAL", "RUMOR") e **fonte na tela**.
Sempre diferenciar oficial × rumor: o vídeo de "vazamento" acima mostra imagens que não são do jogo;
copiar isso arrisca a credibilidade do canal e pode violar políticas de desinformação.

## 3. Gameplay
**Observado**
- Comparação de FPS — 8,9 mi com 6,3 mil inscritos, 16 s; "o que queríamos × o que temos" — 7,4 mi, 12 s:
  tela cheia, texto de contraste em 2 linhas com brilho (roxo → verde).
- Gameplay em 4K 60 fps no console novo — 9,4 mi com 14 mil inscritos, 12 s (vitrine gráfica).
- Longos: séries numeradas de 49–73 min (título "JOGO GAMEPLAY #N").

**Recomendação**: curto = um momento só (10–20 s), visual impressionante ou contraste; nada de intro.
Longo = série numerada com título de objetivo ("comprando a casa mais cara").

## 4. Curiosidades / Segredos
**Observado**
- Fatos secretos — 14,4 mi, 37 s: tela cheia, **uma palavra por vez**, palavra-chave colorida, corte a cada ~5 s.
- "Você sabia" — 3,6 mi, 14 s, em série numerada (BR).
- Detalhe de GTA 6 — 1,4 mi com 1,3 mil inscritos, 18 s.
- Longos: listas de easter eggs com capítulo por item (40–106 min) ou lista curta de segredos em 6 min.

**Recomendação**: gancho "Você sabia que…?" + prova visual + zoom no detalhe; série numerada.

## 5. Compilados / Rankings
**Observado**
- Ranking de momentos — **27,8 mi com 15 mil inscritos**, 55 s: fundo preto, título fixo em 2 cores,
  vídeo 16:9 no meio e **lista de 1 a 5 que vai sendo preenchida** a cada clipe (o nº 1 por último).
- Outro ranking do mesmo canal — 890 mil; compilado de falhas — 3,6 mi, 12 s.
- Longos: 8–16 min (compilado de manobras e falhas com 108 mi; capítulos por tipo de momento).

**Recomendação**: ranking com revelação progressiva prende até o fim (curiosidade pelo nº 1).
Clipes de 3–8 s; usar só material próprio ou com permissão (compilados de terceiros são o maior risco de
reivindicação de direitos autorais).

## O que virou função no Clipador
| Achado | Função |
|---|---|
| Cada categoria tem duração, layout e legenda típicos | **Presets de formato** (curto e longo) ao criar o projeto |
| Ranking 1–5 revelado aos poucos | **Overlay de ranking** (rótulo por trecho) |
| Selo fixo de notícia / título fixo | Gancho com duração 0 = fixo o vídeo todo |
| Longos organizados em capítulos | **Rótulo por trecho → capítulos do YouTube** (exportação + cartela na tela) |
| Estrutura de cada formato | **Guia do formato** com roteiro-modelo e checklist |
| Botão do controle na tela (guias) | Planejado: overlays de imagem (precisa de biblioteca de ícones) |
| Moldura temática (notícias) | Planejado: fundo personalizado no layout empilhado |
