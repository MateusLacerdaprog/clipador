# CLAUDE.md - Diretrizes do Projeto GTA 6 Shorts Viral

Este repositório contém a pipeline completa de produção de vídeos curtos (YouTube Shorts, TikTok, Instagram Reels) para análise do trailer oficial de GTA 6, sincronizado com narração do usuário gravada em estúdio desktop próprio.

---

## 🚨 REGRAS CRÍTICAS E OBRIGATÓRIAS (NUNCA VIOLE)

1. **JAMAIS DECLARAR O VÍDEO COMO "PRONTO" OU "FINAL" PREMATURAMENTE:**
   - Toda renderização gerada é estritamente um `RASCUNHO` para avaliação do usuário.
   - Sempre gere quadros de revisão (PNG) ou vídeo `RASCUNHO_*.mp4` e peça a revisão e aprovação explícita do usuário antes de qualquer export definitivo.

2. **PADRÃO DE LEGENDAS (SHORTS VIRAIS / RETENÇÃO)** — editor Clipador (gameplay/trailer, inclusive os vídeos atuais de GTA 6):
   - **Segmentação por pausas naturais:** Use `faster-whisper` com quebra em pausas/silêncios ($\ge 0.35$s), no máximo 5 palavras por cartão e no máximo 34 caracteres.
   - **Proibido fatiamento arbitrário:** NUNCA fatie arbitrariamente palavras ou force duração mínima artificial (ex: 0.6s), pois isso faz a próxima frase vazar na tela antes do tempo.
   - **Estilo Visual:** Formato ASS com efeito karaokê real (`\k` com destaque em amarelo `#FFDE00`, texto base branco `#FFFFFF`, fonte `Arial Black` tamanho 88, contorno preto espesso 7px, sombra 2px).
   - **Zona Segura (Safe Zone):** Posição vertical $y=1330$ (área segura do YouTube Shorts: livre de botões laterais de like/comentário e do rodapé com nome do canal/som).
   - **Zero sobreposição:** Intervalos de tempo estritamente sequenciais.

3. **ENQUADRAMENTO VISUAL (1080x1920)** — editor Clipador:
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
python -m pytest tests -q     # 286 testes (~12 min). OBRIGATÓRIA antes e depois de qualquer mudança e antes de concluir.
python -m clipador montar NOME --fonte VIDEO [--formato X] [--layout Y] [--trechos 14-20,31-36 | --pedido "fala"] [--referencia ID]
python -m clipador finalizar NOME [--narracao voz.wav]    # legendas da narração + RASCUNHO novo (FINAL nunca)
python -m clipador referencia NOME   # mede os vídeos de referencias/videos/NOME/ e cria o perfil
python -m clipador reels NOME --top conta:ID ... [--controle conta:ID ...]   # baixa Reels (yt-dlp), mede e apaga
python -m clipador canal|ideia|roteiro|esteira|metricas|experimento|custo ...   # estúdio CPV (docs/cpv/10-manual-operacional.md)
python -m pytest tests -q -m "not lento"   # ciclo rápido enquanto edita: 223 testes (~100 s), sem render nem transcrição
```
- **Fluxo do usuário (18/10/2026):** ele pede o vídeo na conversa; o Claude monta com `clipador/automacao.py` (mesma API da tela, em processo) até o RASCUNHO sem narração; o usuário grava a narração na aba 5 (ou manda o arquivo) e o Claude roda `finalizar`. O app na tela é para ajustes. O agente não escreve título nem legenda à mão; FINAL só com aprovação no app.
- **GTA 6 / Take-Two:** a política oficial só tolera uso NÃO comercial; não monetizar material de GTA sem licença escrita (canal 4).
- Testes lentos: todo teste que renderiza (render/quadros/prévia/exportar, câmera do React) ou transcreve leva `@pytest.mark.lento` (marcador registrado em `tests/conftest.py`). Teste novo que renderiza também leva. O ciclo rápido não substitui a suíte inteira.
- Status, riscos e plano por fases: `clipador/docs/AUDITORIA.md` (atualize os estados ✅/🟡/📋 ao concluir algo).
- Segurança (não remover): middleware em `web/app.py` só aceita Host local e recusa comandos de outros sites; toda entrada que vira parâmetro do FFmpeg é validada (`app.py`, `audio.validar`, `projeto.CROP_RE`).
- **Git (desde 18/10/2026):** repositório nesta pasta, identidade genérica `Clipador <clipador@localhost>` (nunca o e-mail da conta), `main` = estado inicial e trabalho em ramos (`cpv-implementacao`); 1 commit por item, sem push. Antes de cada commit: varrer por e-mail, caminho pessoal (C:\Users\...) e chaves. Fora do Git (.gitignore): projetos/, estudio/, vídeos/áudios, _versoes/, config/, kits/, modelos/, `.claude/launch.json`. Zips em `_versoes/` continuam como backup extra.
- Bug conhecido do FFmpeg 9: não usar `zoompan` (gera quadros a mais e desalinha a montagem); o zoom lento é `scale` com `eval=frame` em `layouts.tela_cheia`.
- **Referência detalhada por área** (estúdio CPV, referências/Reels, código e rotas, publicação, verificador, IA e chaves, React, legendas, timeline, kits, zoom, áudio, render, editonny/motion, interface): `clipador/docs/GUIA_CODIGO.md` — leia a seção da área antes de mexer nela.
- IA: chaves SÓ no cofre do Windows (`keyring`) ou variável de ambiente, nunca em arquivo/log/navegador.
- editonny só para vídeo de pessoa falando; textos de cena sempre do usuário; FINAL só com aprovação (detalhes no guia).

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






