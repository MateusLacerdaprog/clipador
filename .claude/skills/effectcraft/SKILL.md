---
name: effectcraft
description: Gráficos de motion (títulos com pop, texto animado por letra/palavra, contador, círculo "olha aqui", flash de corte) feitos no EffectCraft — motor local estilo After Effects, open source — como camada transparente 9:16 sobre a montagem do Clipador. Use quando o usuário pedir motion, texto animado, destaque animado ou efeito de transição num Short, ou quando os gráficos do editonny não servirem / forem lentos demais.
---

# effectcraft (motion graphics para o Clipador / editonny)

O EffectCraft 0.10 (`C:\Program Files\EffectCraft`, MIT OR Apache-2.0) tem uma CLI completa: modelo de objetos
estilo After Effects em JSX (`script`), 731 comandos, 307 efeitos, presets de animação de texto e render WebM com
alfa. Não precisa de engenharia reversa: tudo passa pela interface pública `effectcraft-cli.exe`.

Esta skill gera gráficos no MESMO formato dos gráficos do editonny (WebM VP9 1080×1920 com `alpha_mode=1`) e os
registra em `projeto.graficos`: o render do Clipador já os põe sobre a montagem e sob a legenda, e a aba 7 lista,
move e remove cada um como os demais.

## Uso

```bash
python .claude/skills/effectcraft/ec_grafico.py receitas
python .claude/skills/effectcraft/ec_grafico.py quadros --receita titulo --texto "<do usuário>" --saida previa.png
python .claude/skills/effectcraft/ec_grafico.py gerar --receita titulo --texto "<do usuário>" --projeto NOME --inicio 3.2 --duracao 2.5
python .claude/skills/effectcraft/ec_grafico.py gerar --receita circulo --x 700 --y 820 --raio 150 --projeto NOME --inicio 8
```

Receitas: `titulo` (pop com overshoot), `texto` (`--animacao typewriter|fadeUpCharacters|bounceInWords|trackingIn|scramble|blurIn|jitter|dropInLines`),
`contador` (`--de --ate --sufixo`), `circulo` (desenha em volta de `--x --y`), `flash` (0,3–1 s, cobre a tela).
Opções comuns: `--cor #RRGGBB` (padrão `#FFDE00`, o amarelo da regra 2), `--tamanho`, `--x`, `--y`, `--duracao`.

## Regras

1. **Texto é sempre do usuário** (CLAUDE.md, memória `feedback-sem-texto-escrito-pelo-agente`). Peça o texto; o
   script recusa `titulo`/`texto` sem `--texto`. Revise o português com quadros em tamanho real.
2. **Posição:** o padrão `y=230` fica na faixa de cima, acima do bloco nítido (y=300 no layout empilhado). Nunca
   ponha gráfico na faixa da legenda (y≈1250–1420) nem colado no rodapé; título e legenda nunca se sobrepõem.
3. **Revise antes de registrar:** rode `quadros` (início/meio/fim sobre cinza), olhe a imagem e só depois `gerar
   --projeto`. Depois gere quadros/RASCUNHO pelo Clipador. Tudo continua RASCUNHO até a aprovação (regra 1).
4. Só curto (9:16): o longo é recusado. Máximo de 40 gráficos por projeto (o mesmo limite do editonny).
5. Para efeitos além das receitas, escreva JSX com o modelo AE (`effectcraft-cli script X.jsx --empty --save-as
   P.ecproj`) e renderize com `render --project P.ecproj --comp G --format webm --channels rgba --audio off`.
   Liste efeitos com `effectcraft-cli exec effect.list --params '{"filter":"glow"}' --empty`.

## Armadilhas do EffectCraft (descobertas testando)

- Em camada de forma, `layer.property("Position")` pega o transform do **grupo** interno. Use
  `layer.property("Transform").property("Position")`.
- Presets de texto não estão no JSX: aplique com `run layer.applyTextPreset '{"layer":"T","preset":"..."}' --save`.
- Expressão em `Source Text` funciona (`linear(time, ...)`), mas monte a string inteira e escape uma vez só.
- `render-frame` sem `--transparent` mostra fundo preto; o WebM sai com alfa mesmo assim.
