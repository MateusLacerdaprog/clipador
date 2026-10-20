# editonny no Clipador (19/10/2026)

**O que é:** skill de edição de vídeo por conversa, criada por Matheus Gomes (repositório
`github.com/soumatheusgomes/editonny`). Inclui transcrição, cortes por forma de onda, limpeza de pausas,
legendas, enquadramento, áudio e uma biblioteca de **145 cenas animadas** (HTML/GSAP renderizadas pelo HyperFrames).

## Instalação (VERIFICADO nesta máquina)
| Item | Valor |
|---|---|
| Commit instalado | `05d3dedcddcf6717001b0a3ef91411ec08f614d4` (19/10/2026), versão 1.0.0 |
| Impressão digital do pacote (SHA-256 do instalador) | `96b7d3def090b83a235767faa9a9d8c98384c24182b994a87ff0d5f451061cef` |
| Onde fica | `~/.local/share/editonny` (fora do OneDrive e do Git: ~0,5 GB de cenas, vídeos e sons) |
| Registro no Claude Code | `~/.claude/skills/editonny` (junção de pasta; o symlink do instalador exige o Modo de Desenvolvedor do Windows) → `/editonny` |
| Dependências | `uv` (Astral, winget), ambiente Python do motor em `engine/.venv` (`uv sync --locked`), FFmpeg, Node 24 |
| Diagnóstico | `editonny.py doctor` OK; `media status` 79/79 vídeos íntegros (SHA-256 do manifesto) |
| Telemetria | HyperFrames com telemetria **desligada** (`hyperframes telemetry disable` + `HYPERFRAMES_NO_TELEMETRY=1`/`DO_NOT_TRACK=1` em toda chamada do Clipador) |

Revisão antes de instalar: sem hooks; o instalador só copia o pacote e cria o registro. Ajudantes que acessam a
internet: `fetch_images` (Wikimedia/Pexels), `gen_image` (OpenRouter), `gen_music`/`gen_sfx` (ElevenLabs), e o
`build.py prepare` baixa o GSAP fixado (jsDelivr). **O Clipador não usa os ajudantes pagos** e nenhuma chave vai para
`.env` (regra do projeto: chaves só no cofre do Windows). O primeiro render baixa o HyperFrames na versão fixada
pelo editonny (`hyperframes@0.8.171`) e o navegador de render.

Atualizar: baixar a versão nova, revisar o diff e rodar o `install.py` dele (a versão anterior fica em
`~/.local/share/editonny-backups`). Como o registro é uma junção, o `install.py` o trata como "não é dele": apague
a junção `~/.claude/skills/editonny` antes e recrie depois (`mklink /J`).

## Licenças (do próprio pacote, THIRD_PARTY_NOTICES)
Código do editonny: MIT. Cenas, fundos e objetos giratórios: criados para o pacote. 3dicons: CC0. Efeitos
(Freesound) e músicas (HoliznaCC0, FreePD): CC0. Fontes: SIL OFL / Apache 2.0. Modelos: YuNet (MIT), MediaPipe
(Apache 2.0). Cada gráfico gerado entra no projeto com `direitos.origem = "licenciado"` e o link do repositório.

## Como entra no Clipador (o que faz sentido para Shorts e para o Instagram)
O Clipador continua dono da montagem, das legendas (regra 2: karaokê amarelo em y=1330), do áudio (regra 4), do
layout (regra 3) e da aprovação (regra 1). Usar o pipeline inteiro do editonny duplicaria tudo isso e quebraria as
regras. Por isso entram só as partes que o Clipador não tinha:

1. **Gráficos animados sobre a montagem** (`core/editonny.py`, `projeto.graficos`): a cena é renderizada com fundo
   transparente (`.mov` ProRes 4444 → WebM VP9 com alfa, ~2 MB por 6 s) e o render a sobrepõe **depois do logo e
   antes da legenda**. Serve para Shorts e Reels (as cenas são 9:16); no vídeo longo (16:9) é recusado. Bons usos
   nos canais: `solar-system` (Como o Espaço Funciona), `three-steps`/`step-by-step` (explicadores),
   `text-number-badge` (rankings), setas/círculos (`pointer-*`) para apontar algo no jogo, transições.
   - **Textos são do usuário.** As cenas trazem exemplos em inglês (títulos, preços, números). A geração recusa
     enquanto houver texto de exemplo; o usuário diz o texto (ou apaga com `""`).
   - O Verificador avisa quando o gráfico disputa o alto da tela com o título do início, passa do fim do vídeo,
     sumiu, ou quando uma cena de tela cheia fica sob a legenda.
2. **Narração sem pausas** (`tighten_cut` do editonny): plano primeiro (só mostra), depois aplicar grava
   `narracao_sem_pausas.wav` e o projeto passa a usá-la; Desfazer volta à anterior. Pausas ≥ 0,25 s viram 0,15 s
   (ajustável). **Cuidado:** a narração gravada sobre a montagem (aba 5) fica adiantada em relação à imagem; o
   aperto serve para a narração que vem antes da montagem (roteiro → narração → montagem, os canais do CPV).
3. **Versão 4:5 para o feed do Instagram** (`render.exportar_4x5`, botão na aba 7): 1080×1350 recortado do
   RASCUNHO/FINAL, com a mesma faixa da 1:1 (título, ação, legenda) e mais altura. O Reels continua sendo o 9:16.

Fica de fora de propósito: legendas do editonny (as do Clipador seguem a regra 2), cortes automáticos do vídeo-fonte
(o Clipador já tem a timeline), troca de voz, geração de imagem/música paga, recorte de pessoa (o React já tem).
Para um vídeo de **câmera falando** (Reels de rosto), o editonny inteiro pode ser usado direto pela skill
`/editonny`, fora do Clipador, e o MP4 dele entra no Clipador como fonte para publicar (aba 7).

## Editor editonny por projeto (pessoa falando)
Decisão do usuário (19/10/2026): cada projeto escolhe quem edita (aba 7 → "Quem edita este vídeo"). O editonny é
usado **só** em vídeo gravado com uma pessoa falando: transcrição local (Whisper `small`), EDL com uma faixa por frase
dentro dos trechos da timeline, `waveform_cut` (pausas e respirações), `render_cut`, enquadramento por rosto,
legenda e layout do editonny, render do HyperFrames → `RASCUNHO_<nome>.mp4`. Menos de 8 palavras ou voz em menos de
30% do tempo = recusa ("use o editor do Clipador"). Os vídeos de gameplay/trailer (GTA 6) continuam no Clipador.
Trabalho em `projetos/<n>/editonny/` (o Claude pode refinar com `/editonny`). O FINAL é a cópia do rascunho aprovado.
Testado com uma narração real de 16 s: saiu 13,8 s, 1080×1920, com legenda.

## Motion automático (skill effectcraft do usuário, 20/10/2026)
Depois do render do editonny, `core/motion.py` planeja e queima títulos de motion feitos pela skill
`.claude/skills/effectcraft` (EffectCraft 0.10, WebM com alfa): abertura com a 1ª frase falada (ou um pedaço de 3–5
palavras que não termina em artigo/preposição), pergunta/exclamação curta inteira no meio, contador quando um número
é falado e o fim da última frase. Só palavras da transcrição; amarelo `#FFDE00`, y=230 (acima do rosto, longe da
legenda); mínimo 1,8 s de tela; sem sobreposição. Caixa "Motion automático" na aba 7 desliga.
Comparação real (vídeo de 47 s de pessoa falando): `projetos/cliente-dentista-antes` (só editonny) ×
`projetos/cliente-dentista-depois` (editonny + effectcraft: 3 títulos).

## Aprovação
Botão ✅ Aprovação na lateral: rascunhos de todos os projetos ("Esperando você") e FINAIS ("Aprovados"). Aprovar
gera o FINAL (e o PUBLICACAO.md); "Pedir ajuste" grava o recado em `projeto.revisao_nota`. Nada é publicado.

## Comandos
```bash
python -m clipador editonny status
python -m clipador editonny cenas solar            # o catálogo é em inglês: busque "map", "steps", "arrow"...
python -m clipador editonny grafico NOME solar-system --inicio 4 --duracao 3 --param title="O Sol"
python -m clipador editonny remover NOME 0
python -m clipador editonny apertar NOME           # só o plano
python -m clipador editonny apertar NOME --aplicar
python -m clipador editonny desfazer-aperto NOME
```
API: `GET /api/editonny`, `GET /api/editonny/cenas?busca=`, `POST/PUT/DELETE /api/projetos/{n}/graficos[/{i}]`,
`POST /api/projetos/{n}/narracao/apertar` (`aplicar`, `pausa_max`, `pausa_min`), `.../apertar/desfazer`,
`POST /api/projetos/{n}/exportar_4x5`.

## Limites conhecidos
- Gerar um gráfico leva ~1–2 min (HyperFrames abre um navegador por baixo). Uma cena por vez.
- A transparência depende de trocar o fundo preto do `index.html` gerado; se uma versão nova do editonny mudar
  isso, a geração para com erro claro (não sai gráfico opaco escondido).
- Os parâmetros são trocados no bloco `var P` da cópia da cena; versões novas podem mudar nomes (erro claro também).
- Testado: cena `solar-system` real sobre um rascunho, aperto real de uma narração com pausas, 4:5 em tela cheia e
  empilhado (`tests/test_editonny.py`). As outras 144 cenas não foram renderizadas uma a uma.
