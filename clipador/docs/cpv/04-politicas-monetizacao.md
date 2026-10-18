# 04 — Políticas de monetização e matriz de conformidade (Fase 5)

Verificado em **18/10/2026** nas páginas oficiais abaixo (as páginas de ajuda não mostram data de atualização; o
rodapé diz ©2026). **Oficial** = texto do YouTube; **Interpretação** = nossa leitura para o Clipador.
Nada aqui é parecer jurídico. Cumprir as regras **não garante** entrada nem permanência no YPP: a revisão é
humana e olha o canal inteiro.

## Fontes oficiais consultadas
| # | Página | URL | Situação |
|---|---|---|---|
| F1 | Políticas de monetização de canais | https://support.google.com/youtube/answer/1311392 | ativa (link do pedido) |
| F2 | Visão geral e elegibilidade do YPP | https://support.google.com/youtube/answer/72851 | ativa |
| F3 | Políticas de monetização dos Shorts | https://support.google.com/youtube/answer/12504220 | ativa |
| F4 | Divulgação de conteúdo GenAI/alterado | https://support.google.com/youtube/answer/14328491 | ativa |
| F5 | Política de spam | https://support.google.com/youtube/answer/2801973 | ativa |
| F6 | Engajamento falso | https://support.google.com/youtube/answer/3399767 | ativa |
| F7 | Diretrizes para anunciantes | https://support.google.com/youtube/answer/6162278 | ativa |
| F8 | Uso aceitável (fair use) | https://support.google.com/youtube/answer/9783148 | ativa |
| F9 | Conteúdo "para crianças" | https://support.google.com/youtube/answer/9528076 | ativa |
| F10 | YPP (YouTube for Creators) | https://www.youtube.com/creators/earn/youtube-partner-program/ | ativa |
| F11 | Blog oficial: mudanças no YPP (10/08/2026) | https://blog.youtube/news-and-events/youtube-partner-program-updates-2027-new-opportunities-earn/ | ativa |
| F12 | Hub de criadores | https://www.youtube.com/creators/ (ponto de partida pedido; leva a F10) | ativa |

Cobertura secundária usada só para cruzar (não como fonte): [Newsshooter](https://www.newsshooter.com/2026/08/10/youtube-updates-its-partner-program/),
[Switcher Studio](https://www.switcherstudio.com/whats-new/youtube-partner-program-changes-2027) — divergem em detalhes; vale o F11.

## O que muda o negócio (Oficial)
1. **Hoje (até 31/01/2027):** anúncios exigem 1.000 inscritos + 4.000 h (longos, 12 meses) **ou** 10 mi de views
   qualificadas de Shorts em 90 dias (F2, F10). Nível menor (assinaturas, Supers, Shopping, parcerias): 500
   inscritos + 3 envios em 90 dias + 3.000 h **ou** 3 mi de views de Shorts em 90 dias (F10).
2. **A partir de 01/02/2027 (F11):** novos candidatos precisam de **8.000 h em 365 dias ou 20 mi de views de
   Shorts em 90 dias** (o post não repete o requisito de inscritos; cobertura secundária diz que os 1.000
   continuam). E **toda** receita de Shorts passa a exigir **10 mi de views qualificadas de Shorts nos últimos
   90 dias**; abaixo disso o canal segue no YPP ganhando nos vídeos longos e volta a ganhar nos Shorts ao
   passar de novo. Quem já está no YPP não perde o status. Nível menor: sem mudança.
3. **Revisão:** sistemas automáticos + revisores humanos avaliam o canal inteiro; ~1 mês; recusado → recurso
   em 21 dias ou novo pedido em 30 dias (90 se reincidente) (F2). Monetização pode ser desligada após 6 meses
   sem envios.
4. **Dinheiro dos Shorts (F3):** fundo do feed → parte para música; **sem música, 100% da fatia vai ao fundo**;
   1 faixa de parceiros = metade; 2 faixas = um terço. O criador recebe pela fatia de "views engajadas" e fica
   com **45%**. Short com **mais de 1 minuto e reivindicação de direitos (Content ID) não monetiza**. Views
   artificiais e Shorts não originais (clipe sem edição, reupload, compilação sem conteúdo original) não contam.
5. **Interpretação:** um canal dark **só de Shorts começando agora** dificilmente chega a 10 mi/90 dias antes de
   fevereiro; depois precisa de 20 mi/90 dias para entrar e 10 mi/90 dias para continuar recebendo dos Shorts.
   O caminho realista combina **Shorts (descoberta) + vídeos longos (horas de exibição e receita)** e o nível
   menor do YPP (500 inscritos / 3 mi de views) para assinaturas e parcerias.

## Matriz de conformidade

| Regra (fonte) | Risco | Exemplo de violação | Prevenção | Verificação automatizável no Clipador | Revisão humana obrigatória |
|---|---|---|---|---|---|
| **Conteúdo inautêntico/repetitivo** — "feito com modelo", "intercambiável de vídeo a vídeo"; não: slideshow de imagens, histórias templadas, texto rolando sem narrativa (F1) | **Canal inteiro** perde monetização | 30 Shorts de IA com mesmo roteiro-modelo, mesma voz, mesma música | Série com moldura fixa mas **caso, ângulo e roteiro diferentes**; narração própria; edição com intenção | Similaridade entre roteiros do mesmo canal (alerta > limiar); contagem de vídeos com mesma música/voz/estrutura; proporção de imagens estáticas sem movimento/narração | Sim: o canal "parece intercambiável"? |
| **IA em massa** — "conteúdo de IA com modelos genéricos que dá impressão de produção em massa" não monetiza; IA para editar roteiro ou gerar fundo único é aceita (F1); produção sintética em massa é spam (F5) | Canal | Gerar 10 vídeos/dia do mesmo prompt | Limite de publicação por canal (padrão 1/dia), aprovação humana de cada roteiro, registro do que foi feito por IA | Contador por canal/dia; registro de etapas por IA no histórico do roteiro | Sim |
| **Persona de IA como especialista** em saúde, direito, finanças, política não monetiza (F1) | Canal/vídeo | Avatar "médico" de IA dando conselho | Não usar persona de especialista; citar fontes | Palavras de domínio sensível + voz sintética → bloquear | Sim |
| **Conteúdo reutilizado** — repropor conteúdo do YouTube/outra fonte sem valor original significativo; aceito: crítica, reação com comentário (F1, vídeo oficial V4) | **Canal inteiro** | Trailer cortado com música por cima; clipes de série sem narrativa | Narração/comentário em todo o trecho de terceiros; trecho curto; transformação clara | Proporção de tempo com fonte de terceiros **sem** narração/comentário sobre ela; fontes marcadas como "terceiros" | Sim: há "diferença significativa"? |
| **Direitos autorais / fair use** — crédito e "não tenho direitos" não criam fair use; claim pode bloquear receita; Content ID não decide fair use (F8) | Claim/strike; Short > 1 min com claim não monetiza (F3) | Música comercial no fundo; gameplay de terceiros sem comentário | Biblioteca de áudio do YouTube ou trilhas licenciadas; música própria; registro de licença | Todo arquivo de mídia com origem + licença; **Short > 60 s com fonte "terceiros" → alerta** de não monetização se houver claim | Sim, para qualquer uso de obra de terceiros |
| **Música reduz a fatia do criador** no fundo dos Shorts (F3) | Receita menor (não é violação) | 2 faixas de parceiros num Short | Usar música só quando agrega; preferir sem música licenciada de parceiros | Contar faixas de música da biblioteca usadas no Short e mostrar o efeito | Não |
| **Divulgação de conteúdo sintético realista** — pessoa real dizendo o que não disse, evento real alterado, cena realista que não ocorreu, música de IA como foco (F4). Não precisa: animação/fantasia, IA no roteiro/legenda/título, **clonar a própria voz**, footage de videogame | Rótulo aplicado; repetição → remoção/saída do YPP | Vídeo realista de IA de um jogador real "fazendo" algo | Marcar "Uso de IA" no Studio quando aplicável | Checklist: tem pessoa real? evento real alterado? cena realista gerada? → exige declaração | Sim (a declaração é do usuário) |
| **Spam/metadados enganosos** — título/miniatura que engana; clickbait malicioso (F5) | Remoção, strike | "Trailer 3 vazado" sem existir | Gancho verdadeiro; título cumpre o que o vídeo mostra | Gancho/título com termos de alto risco ("vazado", "oficial") exige fonte registrada | Sim |
| **Repostar/variações em massa** — poucas variações ok, alto volume com mínimas mudanças não (F5); apagar e repostar arrisca spam (V5) | Spam | Apagar e repostar o mesmo Short até "pegar" | Nunca repostar igual; fazer versão melhor | Hash de conteúdo do RASCUNHO/FINAL: bloquear exportar duplicado do mesmo canal | Não |
| **Evasão de detecção** — acelerar áudio, filtros pesados, cortar para fugir da detecção (F5) | Remoção | Espelhar e acelerar clipe alheio | Nunca usar transformações para esconder origem | Proibir no app presets de "espelhar/acelerar" sobre fonte de terceiros | Não |
| **Engajamento falso / incentivo** — comprar views, sub4sub, recompensar por likes; pedir like/inscrição é permitido (F5, F6) | Strike, encerramento | Sorteio por inscrição | Pedir engajamento de forma natural, sem prêmio | Bloquear termos de sorteio/recompensa em CTA; nenhuma automação de comentários/views | Não |
| **Diretrizes para anunciantes** — 14 temas (palavrão, violência, choque, atos perigosos, ódio, drogas, armas, temas controversos, eventos sensíveis, desonestidade, inadequado para crianças, incendiário, tabaco); título/miniatura/descrição contam; violência gráfica nos **primeiros 7 s** ou miniatura pode zerar anúncios (F7) | Anúncios limitados ou zerados | Morte violenta no gancho | Gancho sem violência gráfica; palavrões fora do título | Lista de termos por categoria no roteiro/título; alerta para os 7 primeiros segundos | Sim |
| **Feito para crianças (COPPA/FTC)** — declaração obrigatória do criador, responsabilidade dele (F9) | Legal (multa FTC), recursos desligados | Animação infantil marcada como "não" | O usuário decide; app nunca preenche | Já implementado: publicação exige a escolha explícita | Sim (sempre) |
| **Elegibilidade/limiares** (F2, F10, F11) | Sem receita | Contar com receita de Shorts sem 10 mi/90 dias | Plano financeiro com cenário "sem receita de Shorts" | Painel com views de Shorts dos últimos 90 dias (quando houver acesso ao Analytics) | Não |

## O que o Clipador **não** pode prometer
- Que um vídeo/canal será aceito no YPP (revisão humana do canal inteiro, F2).
- Que um uso de terceiros é fair use (só tribunal decide, F8).
- Que ausência de reivindicação de direitos = apto a monetizar.
- Que o rótulo de IA não afeta nada além do que o YouTube diz (F4: não limita audiência nem elegibilidade por si).
