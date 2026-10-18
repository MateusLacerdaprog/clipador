# OpusClip × Clipador — o que copiar (ideias), o que não

Fonte: páginas públicas do OpusClip (opus.pro, 16/10/2026) e resenhas. **Não** foi feita engenharia reversa do
serviço (é um SaaS: a lógica roda no servidor deles e não é observável). Reimplementamos *funções*, nunca código,
marca ou visual deles. Playsquad **não** é ferramenta de clipes (é app de interação ao vivo para streamers):
ficou de fora; se a ideia era outro produto (ex.: Eklipse), informe o nome.

| Função do OpusClip | Clipador hoje | Vale? | Proposta |
|---|---|---|---|
| Achar trechos bons num vídeo longo | Cenas + energia de áudio (nota 0–100) | **Sim** | Destaques de jogo: picos de áudio (explosão/grito), movimento, + transcrição local (Whisper). Lista ordenada com o motivo de cada nota |
| Clipar por prompt ("o momento da perseguição") | — | **Sim** | Pedir à IA (texto da transcrição + rótulos de cena; nada de vídeo) e mostrar os trechos sugeridos para aprovar |
| Virality score | — | **Parcial** | Nota é opaca e não garante resultado. Fazer "nota de retenção explicável": critérios medidos (gancho nos 3 s, ritmo de cortes, duração, fala) comparados com o perfil de referência |
| Reframe com rastreio de rosto/objeto | `foco_x` manual | **Sim** | Foco automático por movimento (OpenCV, local) em jogos; sem rosto |
| 1:1 / 16:9 / 9:16 | 9:16 e 16:9 | **Sim (pequeno)** | Adicionar 1:1 (1080×1080) |
| Legendas animadas editáveis | Feito (3 estilos, presets, tempo por palavra) | ✅ | — |
| Brand template (fonte, cor, logo, intro/outro) | Estilo por projeto | **Sim** | "Kit do canal": salvar estilo + logo + intro/outro e aplicar em novos projetos |
| Editor por texto (apagar palavra = cortar) | Legenda editável, corte por trecho | **Sim, alto valor** | Cortar pela transcrição (palavras com tempo já existem) |
| Vários clipes de um vídeo em lote | Um projeto por vez | **Sim** | "Gerar N clipes" da lista de destaques, cada um vira projeto |
| B-roll de banco de imagens/IA | — | **Não agora** | Direitos de uso; só biblioteca do próprio usuário |
| Tradução / dublagem | — | **Depois** | Legenda traduzida via IA (texto); dublagem fica fora |
| Agendar e postar nas redes | Só título/descrição/hashtags | **Depois** | Exige login OAuth de cada rede e termos de API; risco alto |
| Exportar XML p/ Premiere | — | **Talvez** | Baixa prioridade (EDL/FCPXML) |
| Entrada por link | yt-dlp | ✅ | — |

## Estado (16/10/2026)
1. ✅ Momentos de jogo (áudio, impactos, movimento, cortes) com motivos — aba Cortes.
2. ✅ Clipar por pedido: busca local na fala (Whisper) ou IA só com texto. A IA não vê a imagem: pedidos puramente visuais ("a perseguição") só funcionam se houver pista na fala ou nos sinais.
3. ✅ Foco automático pelo centro do movimento.
4. ✅ Kit do canal (logo incluso) + versão 1:1 · 📋 intro/outro.
5. ✅ Editar pelo texto (fala da fonte).
6. ✅ Um projeto por momento, em lote.
