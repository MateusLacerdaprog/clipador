# Clipador — arquitetura

Software local (roda no seu PC, abre no navegador) para transformar vídeos de games em
Shorts/TikTok/Reels sem aparecer, com narração opcional da sua voz.

```
 navegador (http://127.0.0.1:8765)            servidor Python (FastAPI)              disco
 ┌──────────────────────────────┐   HTTP   ┌───────────────────────────────┐   ┌──────────────────────┐
 │ web/static  (HTML + js/*.js) │ ───────► │ web/app.py + web/rotas/*.py   │   │ projetos/<nome>/     │
 │  1 Fonte  (importar vídeo)   │          │   tarefas em 2º plano (jobs)  │──►│  projeto.json        │
 │  2 Cortes (cenas sugeridas)  │          ├───────────────────────────────┤   │  proxy.mp4  (prévia) │
 │  3 Narração (grava no navega-│          │ clipador/core/                │   │  narracao.wav        │
 │    dor sobre a prévia)       │          │   midia.py     ffprobe, cenas │   │  legenda.ass         │
 │  4 Legendas (editar palavras)│          │   destaques.py sugere cortes  │   │  quadros/*.png       │
 │  5 Revisar (quadros, rascunho│          │   legendas.py  whisper + ASS  │   │  RASCUNHO_*.mp4      │
 │    aprovar → FINAL)          │          │   layouts.py   9:16 presets   │   │  FINAL_*.mp4         │
 └──────────────────────────────┘          │   audio.py     voz + ducking  │   └──────────────────────┘
                                           │   render.py    monta tudo     │
                                           │   projeto.py   modelo/JSON    │
                                           └───────────────────────────────┘
```

## Organização do código (17/10/2026)
- `web/app.py`: só a segurança (Host local, recusa comandos de outros sites), a página e a ordem dos roteadores.
- `web/comum.py`: utilidades das rotas (carregar projeto, `_estado`, validações de entrada que viram parâmetro do FFmpeg).
- `web/rotas/<área>.py`: um `APIRouter` por área (projetos, fontes, zoom, kits, revisao, react, timeline, audio,
  legendas, ia, referencias, comandos, publicacao). Imports explícitos; a ordem de inclusão importa (primeira rota que casa).
- `web/static/js/*.js`: scripts clássicos por aba/área, carregados em ordem pelo `index.html` (`base.js` primeiro,
  `inicio.js` por último). Função usada no carregamento precisa estar num arquivo anterior (`tests/test_interface.py`).
- Regra de negócio fica em `core/` (ex.: `core/publicacao.py`, `core/timeline.py`); as rotas só validam e chamam.

## Decisões
- **Python + FFmpeg no núcleo** (já instalados, já usados). Toda a lógica de vídeo fica em
  `clipador/core` e não depende da interface — a CLI e o site chamam as mesmas funções.
- **Site local (FastAPI + HTML/JS sem build)**: nada de Node/React para instalar; abre em qualquer
  navegador; o mesmo código pode virar SaaS depois.
- **Gravação de voz no navegador** (MediaRecorder) tocando uma **prévia montada da timeline**
  (`proxy.mp4`, 540p). Assim a voz fica sincronizada com exatamente o que vai para o vídeo final —
  substitui o gravador Tkinter e a extensão do Chrome.
- **Projeto = um JSON** (`projeto.json`) com fontes, segmentos, layout, gancho, estilo de legenda e
  áudio. Tudo é re-renderizável; nada se perde.
- **Fluxo de aprovação obrigatório**: o render gera sempre `RASCUNHO_*.mp4`; só o botão "Aprovar"
  gera `FINAL_*.mp4` (regra do CLAUDE.md).

## Modelo de projeto (projeto.json)
```json
{
  "nome": "gta6-launch-trailer",
  "fontes": [{"id": "f1", "caminho": "...mp4", "crop": "1920:960:0:60"}],
  "segmentos": [{"fonte": "f1", "ini": 14.0, "fim": 17.5, "foco_x": 0.5, "zoom": 1.0}],
  "layout": "tela_cheia | empilhado | comparacao",
  "gancho": {"texto": "O DETALHE QUE NINGUÉM VIU", "ate": 3.0},
  "legenda": {"estilo": "karaoke | palavra | caixa", "...": "..."},
  "audio": {"musica_db": -20, "manter_audio_jogo": true},
  "narracao": "narracao.wav"
}
```

## Presets de layout (1080×1920)
| preset | quando usar | composição |
|---|---|---|
| `tela_cheia` | detalhe/zoom (padrão dos canais pequenos que viralizaram) | recorte 9:16 do quadro, `foco_x` escolhe a área, `zoom` > 1 faz zoom lento |
| `empilhado` | gameplay largo, notícia (padrão de veículos de games) | bloco 1080×864 em y=300 + fundo desfocado (regra atual do projeto) |
| `comparacao` | A × B (GTA 5 × GTA 6 — 3 mi de views em 13 s) | duas fontes em cima/baixo com rótulos |

## Estilos de legenda
| estilo | descrição |
|---|---|
| `karaoke` | cartão de até 5 palavras, palavra falada em amarelo (padrão atual do CLAUDE.md) |
| `palavra` | 1–3 palavras por vez, grandes, no centro |
| `caixa` | frase curta em caixa branca sob o vídeo |

## Atualização (16/10/2026, etapa 2)
Novos módulos: `core/formatos.py` (curto/longo × 5 categorias, ranking, capítulos), `core/audio.py` v2 (4 trilhas,
migração, validação), `core/tarefas.py` com cancelamento. `web/app.py` ganhou proteção local (Host/Origin),
validação de todas as entradas, bibliotecas `musicas/` e `efeitos/`, prévia solo e rotas de formatos/capítulos.
Contratos entre módulos: a interface só fala com a API; a API só altera `projeto.json` por `projeto.salvar`
(gravação atômica); o render só lê o projeto e nunca altera arquivos de origem (saída em `.tmp` + verificação).
O plano por fases e o estado de cada item ficam em `AUDITORIA.md` (fonte da verdade); a lista abaixo é a original.

## Funções por fase (versão original)
**Fase 1 (agora)** — núcleo + site com: importar vídeo (arquivo local ou link), sugestão de cenas,
montar segmentos, gancho de título, 3 layouts, gravar narração sobre a prévia, transcrever e editar
legenda, quadros PNG de conferência, rascunho, aprovar → final.

**Fase 2** — destaques automáticos por IA (pontuar trechos por movimento, áudio e fala, estilo
OpusClip), seta/círculo sobre o detalhe, gerador de roteiro com gancho/loop, título + descrição +
hashtags, exportar 3 plataformas, fila em lote.

**Fase 3** — funções inspiradas em OpusClip/Playsquad (após a análise com a skill REA):
reenquadramento automático por rastreamento de objeto, "virality score", calendário/postagem.
