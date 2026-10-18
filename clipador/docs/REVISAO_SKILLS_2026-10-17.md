# Revisão com as skills de Shorts — 17/10/2026

Skills usadas: `youtube-shorts` (Retention Ladder), `hook-writer`, `short-form-video-script` (WATCH).
Critérios: Stop (gancho 0–3 s) · Hold (retenção, ritmo, loop) · Angle (ângulo próprio) · Bridge (título/descrição/hashtags).

## Achados (valem para todos os vídeos)
1. **Final sem loop** nos vídeos curtos: a skill pede que o último plano leve de volta ao primeiro quadro (replays contam).
   → Corrigido em v02, v03, v09 (último plano repete o primeiro). v06/n01 já terminam em piada, mantidos como o usuário aprovou.
2. **Sem título/descrição de publicação**: faltava palavra-chave no título e hashtags.
   → Gravado em `projeto.json → publicacao` de todos os projetos e listado em `videos prontos/PUBLICACAO.md`.
3. **Gancho enganoso (v04)**: "ALERTA: GTA 6 acaba de lançar o TRAILER 3". O trailer 3 não existe nas fontes; a skill proíbe
   promessa que o conteúdo não cumpre e o YouTube pode tratar como enganoso. **Mantido a pedido do usuário** — recomendo trocar
   por "GTA 6: o trailer em 20 segundos" se o canal quiser evitar risco.
4. **v09 é rumor**: gancho e legenda já dizem "rumor / não é oficial" (ok, honesto).
5. **Legendas começam depois do título** (regra do usuário) → nos primeiros ~2,5 s só o título carrega o gancho; ok porque o
   quadro inicial já é forte. Os três vídeos de humor (v06, n01, w04, w09) têm o título como gancho e o texto na piada.
6. **Ritmo**: a skill recomenda mudança de imagem a cada 2–4 s e 15–35 s no total. Todos os vídeos estão entre 7,5 s e 22 s
   (exceção: v10 e n05, que são o original comentado, 21–36 s).
7. **Conteúdo de terceiros** (v05, v10, n05): precisa de crédito/direitos antes de publicar.

## Aprovados pelo usuário e preservados
v01, v04, v06, v08, v10 (e v02/v03/v05/v09 depois dos ajustes pedidos).

## Correções após o feedback do lote 3
- **Ritmo**: w01–w03 estavam rápidos (planos de 1,4–1,5 s). Agora ≥ 2,2–2,6 s por plano/par; w01 7,8 s, w02 10,5 s.
- **Comparação = tela dividida** (regra do usuário): v08, n04 e w03 (PS1→PS5) foram refeitos no layout `comparacao`
  (PS1…PS4 em cima × PS5 embaixo, legenda "PSx × PS5", rótulos "ANTES"/"PS5"). Memória: `feedback-comparacao-tela-dividida`.
- **Falhas de render** de w05/w07/w10: legenda começava depois do fim do vídeo (API recusa `ini` fora da duração). Resolvido
  alongando os vídeos; o app poderia avisar antes ("legenda além do fim").
- **Cenas com cartão "Rockstar Games Presents"/logo** apareciam em w05, w10 e w01 — trocadas por cenas limpas.
- Limitação conhecida: v08 e n04 ainda mostram o logo "grand theft auto" surgindo na 1ª cena do PS1–PS4 (faz parte do trailer).

## Lote 3 (w01–w10)
Formatos aprovados replicados com material do trailer: comparação A×B (w01, w06), PS1→PS5 (w03), humor rápido (w04, w09),
edit cinematográfico (w08), listas curtas (w02, w05, w07, w10).
