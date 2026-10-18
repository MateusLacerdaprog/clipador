# 10 — Manual operacional: do pedido ao resultado

Fluxo combinado (18/10/2026): **você pede na conversa, o Claude monta pelo Clipador até o RASCUNHO, você grava a
narração e aprova; o app na tela é para ajustes.** Nada é publicado pelo sistema, e o Claude não escreve o texto
final de gancho, legenda ou título sem você pedir/aprovar.

## 0. Uma vez só
```bash
python -m pip install -r requirements.txt
python -m clipador canal semear          # cria os 4 canais (rascunho) da estratégia docs/cpv/05
```
Revise cada canal (nome, público, frequência, `limite_dia`) — pela conversa ("mude a frequência do Mapa Esquisito
para 2 por semana") ou `PUT /api/canais/<id>`. O canal 4 (GTA 6) fica com monetização **sem_receita** até a
resposta da Take-Two (`docs/cpv/rascunho-email-take-two.md`, você envia).

## 1. Ideia (Fase 4.1–4.2)
Peça: *"ideia para o Mapa Esquisito: a fronteira seca de Santana do Livramento, fonte X"*. O Claude registra:
```bash
python -m clipador ideia nova --canal mapa-esquisito --titulo "Fronteira seca Livramento–Rivera" --formato explicador --fonte https://...
python -m clipador ideia avaliar <id> --nota gancho=4 --nota originalidade=4 ... --portao direitos_viaveis=sim ...
```
A nota CPV (0–100) só existe depois dos 4 portões. **Aprovar a ideia é você** (`ideia aprovar <id>` quando disser).

## 2. Roteiro (Fase 4.3)
```bash
python -m clipador roteiro novo <ideia>                 # esqueleto do formato + guia de cada bloco
python -m clipador roteiro bloco <id> gancho "…"        # o texto é seu (ou sugestão da IA que você aplica)
python -m clipador roteiro ganchos <id> "alternativa 1" "alternativa 2"
python -m clipador roteiro afirmacao <id> "fato" https://fonte
python -m clipador roteiro ver <id>                     # mostra a checagem: o que impede aprovar
```
IA opcional: `POST /api/roteiros/<id>/ia` (com o provedor configurado e consentimento) gera uma **sugestão** que
só entra com `/ia/aplicar`; fato sem fonte da ideia vai para "a confirmar". Aprovar = você.

## 3. Projeto, direitos e montagem (Fase 4.4)
```bash
python -m clipador roteiro projeto <id> mapa-livramento   # cria o projeto; o roteiro vai para o teleprompter
python -m clipador montar mapa-livramento --fonte VIDEO --origem proprio --trechos 0-6,10-18
```
Registre a origem de toda mídia (aba 1 → "Direitos deste vídeo", ou `--origem/--licenca`). Música: registre na
biblioteca (`PUT /api/biblioteca/musicas/<arquivo>/direitos`).

## 4. Narração, legendas, revisão (Fase 4.4–4.5)
1. Você grava na aba 5 (sobre a prévia, com o roteiro rolando).
2. `python -m clipador finalizar mapa-livramento` → legendas da sua voz + RASCUNHO novo.
3. Aba 7 → **Verificar**: técnica, retenção e **conformidade** (cada aviso diz a regra oficial, matriz 04).
4. Assista (inclusive "Assistir sem som"), ajuste no app, **aprove o RASCUNHO**, gere o FINAL.
5. `python -m clipador esteira mapa-livramento` mostra em que etapa o projeto está e o que falta.

## 5. Publicação (sempre você)
Publique no YouTube Studio com o texto de `PUBLICACAO.md` (declarações "feito para crianças" e "conteúdo
alterado" são suas). Depois registre o link:
```bash
python -m clipador esteira mapa-livramento --publicado https://youtube.com/shorts/XXXXXXXXXXX
```
Não apague e reposte vídeo que não "pegou" (risco de spam, fonte oficial V5): faça uma versão melhor.

## 6. Resultados (Fase 4.6 e 10)
1. YouTube Studio → Análises → **Modo avançado** → escolha o período e as métricas (views, views engajadas,
   duração média, % assistido, "escolheram assistir", likes, comentários, compartilhamentos, inscritos, receita)
   → **Exportar → CSV** (tabela por vídeo).
2. `python -m clipador metricas importar "Table data.csv" --canal mapa-esquisito` — o importador lista as colunas
   que não reconheceu (nada é descartado). Importe toda semana: cada importação é um retrato datado.
3. Experimento: `python -m clipador experimento novo --canal mapa-esquisito --variavel gancho --metrica views "Gancho com pergunta segura mais que afirmação"`,
   ligue vídeos (`experimento ligar <id> A <video_id>`) e leia `experimento analisar <id>`. Com menos de 10 vídeos
   por variante a resposta é **inconclusivo** — de propósito.
4. Custos: `python -m clipador custo lancar tempo_h 1.5 mapa-livramento` e `custo projeto mapa-livramento --valor-hora 10`.

## 7. Regras que o sistema aplica sozinho
- Limite diário por canal (`limite_dia`, padrão 1 FINAL/dia) — aviso F5.
- Duplicado de projeto já exportado — aviso F5.
- Material de terceiros sem narração, Short > 60 s com material sem licença, música sem licença — avisos F1/F3/F8.
- Termos de risco no gancho/título/legenda dos 7 s (vazado, sangue, palavrão, sorteio…) — avisos F5/F7.
- Roteiro parecido com outro do mesmo canal — aviso F1 (não é prova jurídica de originalidade).
- Chaves de IA só no cofre do Windows; nada sensível em commit, log ou documento.
