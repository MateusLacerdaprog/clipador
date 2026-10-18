# Referências de YouTube (gameplay, GTA, Minecraft) — 17/10/2026

**Método.** Metadados públicos via yt-dlp (sem baixar vídeo): ~60 vídeos mais recentes da aba *Vídeos* de cada canal;
para os 5 longos mais vistos dessa amostra, data de publicação, curtidas e capítulos. Dados brutos:
`pesquisa_youtube_2026-10.json`. **Limites:** amostra pequena e recente (não é o histórico do canal); sem acesso a
CTR, retenção ou receita reais (YouTube Studio é privado); não assisti os vídeos inteiros — estrutura vem de
capítulos e títulos. Legenda: **[O]** observado · **[E]** estimativa · **[I]** inferência.

## 1. Dados observados

| Canal | Inscritos [O] | Longos na amostra [O] | Mediana de views dos longos [O] | Duração mediana [O] |
|---|---|---|---|---|
| [SaninPlay](https://www.youtube.com/@SaninPlay) | 1,35 mi | 59/60 | 61 mil | 13,7 min |
| [AuthenticGames](https://www.youtube.com/@AuthenticGames) | 20,2 mi | 51/60 | 75 mil | 10,1 min |
| [Jazzghost](https://www.youtube.com/@Jazzghost) | 25,0 mi | 59/60 | 2,8 mi | 38,6 min |
| [SSundee](https://www.youtube.com/@SSundee) | 25,5 mi | 59/60 | 653 mil | 20,0 min |
| [MrBeast Gaming](https://www.youtube.com/@MrBeastGaming) | 60,7 mi | 60/60 | 51 mi* | 17,0 min |

\* MrBeast Gaming publica pouco: a "amostra recente" inclui vídeos de 2022–2023.

Destaques [O] (views · duração · publicado · views/dia até 17/10/2026):
- SaninPlay — [GTA 6: tamanho do mapa](https://www.youtube.com/@SaninPlay/videos) 237 mil · 35 min · 03/10/2026 · 16,9 mil/dia;
  "155 DETALHES ABSURDOS" 194 mil · 29 min; "MEGA ANÁLISE do TRAILER: +617 detalhes" 153 mil · **149 min**.
  Todos com **12 capítulos**, "Introdução/Abertura" e um capítulo de **patrocínio**; títulos em MAIÚSCULAS com número e "(Veja!)".
- Jazzghost — roleplay/histórias de Minecraft: 6,4 mi (44 min), 6,0 mi (73 min), 4,6 mi (79 min) em 2–8 semanas,
  **200–330 mil views/dia**; títulos que contam a premissa ("EU SÓ QUERIA VENDER SANDUÍCHE MAS…"); sem capítulos.
- SSundee — séries com mods: 4,3 mi (30 min, SkyFactory), 3,6 mi (19 min, Lucky Blocks); 50–128 mil/dia.
- MrBeast Gaming — desafios: "1,000 Tanks Vs Titan Enderman" 170 mi; "If You Build It, I'll Pay For It" 122 mi com
  capítulos em **escada de valores** ("$100 → $1k → $5k → $10k → $100k builds"); "100 Assassins vs 10 Real Cops" com
  capítulos por **onda/fase**.
- AuthenticGames — Minecraft survival/séries, 8–17 min; os mais vistos da amostra são de 2023–2025 (400–630 mil).

## 2. Potencial de monetização [E]

Premissas (explícitas, **não** são dados dos canais): RPM (receita por mil views) de games em português/Brasil
**US$ 0,30–1,50**; games em inglês/EUA **US$ 1,50–5,00**; vídeos de 8 min ou mais permitem anúncios no meio;
público infantil ("feito para crianças") pode cortar o RPM em 50–80%. Receita estimada = views × RPM ÷ 1000.

| Canal | Vídeo típico (mediana) | Faixa estimada por vídeo [E] | Confiança |
|---|---|---|---|
| SaninPlay (PT) | 61 mil | US$ 18–92 | baixa-média |
| AuthenticGames (PT) | 75 mil | US$ 23–113 (menos se público infantil) | baixa |
| Jazzghost (PT) | 2,8 mi | US$ 840–4.200 (menos se público infantil) | baixa |
| SSundee (EN) | 653 mil | US$ 980–3.270 | baixa-média |

Views ≠ lucro: patrocínios (SaninPlay tem capítulo de anúncio), membros e Shorts mudam muito a conta.

## 3. Formatos: audiência × custo × reprodutibilidade [I]

| Formato | Quem | Audiência | Custo de produção | Dá para reproduzir sem aparecer? | Gera Shorts? |
|---|---|---|---|---|---|
| **Notícia/análise de GTA 6 com ~12 capítulos** | SaninPlay | média, picos em cada anúncio | **baixo** (trailer/gameplay + narração) | **sim** | sim (1 por capítulo) |
| Roleplay/história narrada | Jazzghost | **muito alta** | **alto** (roteiro, atuação, cenários) | parcial (voz sim, mas exige produção) | sim |
| Desafio em escada de valor/dificuldade | MrBeast Gaming | muito alta | alto (servidores, equipe) | parcial | sim |
| Série com mods/progressão | SSundee | alta | médio | sim (gameplay + voz) | sim |

**Recomendação para o canal do usuário (GTA, sem aparecer):** notícia/análise longa com capítulos (padrão SaninPlay)
como base — custo baixo e demanda alta enquanto durar o ciclo de GTA 6 — e cada capítulo virando um Short.
A estrutura em **escada** (MrBeast) e a **premissa no título** (Jazzghost) são técnicas que valem para qualquer formato.

## 4. O que virou ferramenta no Clipador

| Padrão observado | Ferramenta |
|---|---|
| 12 capítulos temáticos, gancho com a revelação mais forte, patrocínio em capítulo próprio | formato longo **Notícias** (estrutura atualizada) + capítulos do YouTube |
| Escada de etapas, premissa em 1 frase, clímax no fim | formato longo **Gameplay/Série** (estrutura atualizada) |
| Capítulo = Short | **Momentos** + "Criar um projeto por momento" + comando "Crie uma versão vertical para Shorts" |
| Ritmo de fala/edição | **Assistente de ritmo** (pausas longas, com "talvez manter") e **Zoom nos picos** |
| Títulos com número e MAIÚSCULAS | Assistente de IA + perfil de referência (já existiam) |
