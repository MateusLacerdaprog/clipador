# 09 — Modelo financeiro e rentabilidade (Fase 11)

Etiquetas: **VERIFICADO** (fonte oficial/código), **ALEGADO** (criador, sem prova), **ESTIMADO** (nossa conta com
hipótese explícita), **HIPÓTESE** (parâmetro que o usuário define). Implementado em `clipador/core/financeiro.py`
(teste: `tests/test_esteira_resultados.py`).

## 1. O que decide se existe receita (antes de qualquer RPM)
1. **Elegibilidade (VERIFICADO, F2/F10/F11):** sem YPP não há receita de anúncios. A partir de **01/02/2027**, canal
   novo entra com 8.000 h/365 dias ou 20 mi de views de Shorts/90 dias; a receita de Shorts só é paga com
   **10 mi de views qualificadas de Shorts nos últimos 90 dias**. Abaixo disso: **receita de Shorts = 0**.
2. **Monetização do canal 4 (GTA 6):** zero por decisão, até haver licença escrita da Take-Two (docs/cpv/05).
3. **Música:** faixa de parceiros reduz a parte do Short no fundo (1 faixa = metade; 2 = um terço) (F3).
4. **Receita é estimada pelo YouTube até o pagamento:** a coluna "Receita estimada" do Studio não é dinheiro na conta.

## 2. Separação obrigatória (como o módulo trabalha)

| Conceito | De onde vem | No Clipador |
|---|---|---|
| Receita projetada | parâmetros digitados pelo usuário | `financeiro.projecao(...)` — sempre rotulada "PROJEÇÃO (hipótese do usuário)" |
| Receita efetivamente recebida | extrato do AdSense/pagamento (fora do app) | lançar manualmente como referência (PENDENTE: campo próprio) |
| Receita estimada observada | CSV do YouTube Studio | `metricas.importar` → `por_projeto()["receita_observada_usd"]` |
| Custos fixos | lançamentos mensais (`fixo_mensal_usd`) | `financeiro.lancar` |
| Custos variáveis | IA (registro real), tempo (`tempo_h`), licenças | `financeiro.lancar` + `ia/uso` |
| Margem estimada | projeção − custos | `projecao()["margem_mensal_usd"]` |
| Lucro realizado | receita observada − custos registrados | `por_projeto()["lucro_realizado_usd"]` (None sem receita importada) |

## 3. Custos por vídeo (ESTIMADO, com as hipóteses à vista)

| Item | Hipótese | Valor |
|---|---|---|
| IA — rascunho de roteiro | 1 chamada, ~1.500 tokens de entrada + ~1.500 de saída; preços da tabela oficial no código (`PRECOS_CLAUDE`, out/2026): Opus 5.5 US$ 4/20 por mi, Sonnet 5.5 US$ 2/10 | Opus 5.5 ≈ **US$ 0,036**; Sonnet 5.5 ≈ **US$ 0,018** |
| IA — transcrição (Whisper) | roda no PC | US$ 0 (custo de energia não medido) |
| Narração | voz do próprio usuário | US$ 0 + tempo |
| Mídia | dados livres (Natural Earth, NASA) e material próprio | US$ 0 + verificação de licença |
| Música | Biblioteca de Áudio do YouTube ou sem música | US$ 0 |
| Tempo do usuário | pesquisa + narração + revisão ≈ 1–2 h/Short (ESTIMADO no plano 07; **medir** com `custo lancar tempo_h`) | depende do valor/hora que o usuário atribuir |

**Leitura:** o custo em dinheiro por Short é desprezível (centavos); **o custo real é o tempo**. Por isso o
painel de custo aceita `valor_hora` (o usuário define) e o modelo diferencia "com tempo" e "sem tempo".

## 4. Receita: o que se sabe sobre RPM (nada inventado)
- ALEGADO (V3, criador BR, sem prova): Shorts no Brasil ~R$ 0,15 por mil views; "gringa" ~R$ 0,70–0,80.
- ALEGADO/dado de terceiros 2023 (V7, estudo de Paddy Galloway citado): ~US$ 0,06 por mil views de Shorts após a
  monetização; vídeos longos US$ 1–2 por mil "como base" (varia muito por nicho).
- Nenhum desses valores é do canal do usuário. **O RPM real só vem do CSV do Studio depois de monetizado.**

## 5. Análise de sensibilidade (não é previsão)
Receita mensal = views/mês × % monetizável × RPM ÷ 1000. Exemplo **só para mostrar a ordem de grandeza** com as
alegações acima, para um canal que já esteja monetizado e passando de 10 mi de views de Shorts em 90 dias
(≈ 3,3 mi/mês, o mínimo da regra de 2027):

| Views de Shorts/mês | RPM (por mil) | Receita/mês | Fonte do RPM |
|---|---|---|---|
| 3,3 mi | R$ 0,15 | ≈ R$ 500 | ALEGADO (V3, Brasil) |
| 3,3 mi | US$ 0,06 | ≈ US$ 200 | ALEGADO/2023 (V7) |

`python -m clipador custo projecao VIEWS VIDEOS_MES RPM [PCT] [CUSTO_VIDEO] [FIXO]` refaz a conta com os números
do usuário. **Conclusão (ESTIMADO):** Shorts sozinhos dão pouca receita mesmo no mínimo de elegibilidade; o
dinheiro relevante tende a vir de vídeos longos (RPM maior), do nível menor do YPP (assinaturas, Supers),
parcerias e produtos próprios — e a dublagem automática PT→EN dos longos é a alavanca a testar (05).

## 6. Critérios de rentabilidade (decisão)
- **Custo por vídeo** (com tempo) × **receita observada por vídeo** (CSV) a cada 30 vídeos por canal.
- Canal continua se a receita observada + valor estratégico (inscritos para o longo) cobre o tempo investido, ou
  se a tendência de views/inscritos por vídeo sobe (critérios do 05). Sem dados reais: **sem conclusão**.
- Nunca usar projeção para "provar" que o negócio dá lucro.
