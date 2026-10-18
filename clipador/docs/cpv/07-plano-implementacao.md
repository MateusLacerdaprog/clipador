# 07 — Plano de implementação (Fases 8–11, ordem da Fase 12)

Princípios: mudanças pequenas e reversíveis; cada item com teste; **núcleo + comandos primeiro** (o usuário
pede pela conversa e o Claude executa — memória "fluxo-comando-aqui"), telas depois para ajuste; nada publica
sozinho; nenhuma promessa de viralização/receita.

## Backlog priorizado

| ID | Prioridade | Item | Depende de | Módulos | Pronto quando | Teste / evidência |
|---|---|---|---|---|---|---|
| I1 | P0 | Repositório Git nesta pasta, `.gitignore` (projetos/, _versoes/, mídia, caches, modelos, config com dados do usuário) e commit inicial do estado atual | **OK do usuário** | raiz | `git log` mostra o estado inicial; cada item abaixo = 1 commit | `git status` limpo após cada item |
| I2 | P0 | `requirements.txt` com versões fixadas do ambiente atual | — | raiz | Arquivo + teste que confere que os pacotes principais importam | `test_qualidade` |
| I3 | P1 | **Registro de recursos e licenças**: cada vídeo/música/efeito/imagem com origem (próprio, licenciado, domínio público, terceiros), licença, link, observação | — | `core/recursos.py`, `projeto.fontes`, rotas fontes/audio | Toda mídia nova pede origem; projetos antigos marcados "não informado" | testes: validação, migração, persistência |
| I4 | P1 | **Conformidade** (matriz 04): termos de risco no gancho/título (F5, F7), violência nos 7 s, Short > 60 s com terceiros, música × fundo (F3), % de tempo de terceiros sem narração, exportação duplicada no mesmo canal (hash), limite diário por canal, checklist de divulgação de IA (F4) | I3 | `core/conformidade.py`, verificador, publicação | Itens aparecem no Verificar e no PUBLICACAO.md com fonte da regra | testes por regra (casos positivo e negativo) |
| I5 | P1 | **Canais**: perfil (idioma, nicho, pilares, formatos, frequência, kit, referência) | — | `core/canais.py`, `canais/<id>.json`, rotas | 3 canais da Fase 6 cadastrados como rascunho | testes CRUD + validação |
| I6 | P1 | **Banco de ideias + pontuação CPV** (portões + 10 critérios com pesos da 03, notas 0–5 com âncora, fontes obrigatórias, status, histórico) | I5 | `core/ideias.py`, rotas, CLI `python -m clipador ideia` | Ideia não sobe de status sem fonte e sem passar nos portões; nota recalculável | testes: pesos somam 100, portão reprova, fonte obrigatória, persistência |
| I7 | P2 | **Gerador de roteiros por formato** (6 esqueletos da 03): campos obrigatórios, 3–5 ganchos, fontes por afirmação, duração estimada por ritmo, versões e aprovação. IA **opcional** (provedor já configurado, com consentimento) só preenche rascunho; **o usuário escreve/aprova o texto final** | I6 | `core/roteiros.py`, `core/ia` | Roteiro aprovado vira projeto (montagem) com fontes ligadas | testes sem IA (esqueleto) e com IA simulada; aprovação obrigatória |
| I8 | P2 | **Similaridade/originalidade** entre roteiros do mesmo canal (texto + estrutura) — alerta, não prova jurídica | I7 | `core/originalidade.py` | Alerta acima do limiar configurável | testes com textos iguais/parecidos/diferentes |
| I9 | P2 | **Esteira com estados**: ideia → roteiro → verificação factual → revisão de direitos → narração → montagem → legendas → QC → aprovação → exportação → publicação autorizada → análise; estado salvo no projeto, trava contra execução duplicada, retomada, log por etapa (sem segredos) | I3–I8 | `core/esteira.py`, `automacao.py` | `python -m clipador esteira <projeto>` mostra e avança etapas | testes: duplicado bloqueado, retomada após falha, log sem chaves |
| I10 | P2 | **Métricas por CSV do YouTube Studio** (exportação do modo avançado; **sem OAuth**): views, visto × deslizado, duração média, % assistido, inscritos, receita/RPM quando houver | — | `core/metricas.py`, CLI | CSV importado vira série por vídeo/canal | testes com CSV de exemplo |
| I11 | P3 | **Experimentos (Fase 10)**: hipótese, variantes, vídeos ligados, linha de base do canal, janela de observação, amostra mínima, comparação com a mediana do canal (intervalo por bootstrap) | I10 | `core/experimentos.py` | Relatório diz "inconclusivo" quando a amostra é pequena | testes de amostra pequena, sem causalidade inventada |
| I12 | P3 | **Modelo financeiro (Fase 11)**: custo por vídeo (IA registrada, tempo, licenças), receita observada (CSV), cenários só com parâmetros digitados pelo usuário | I10 | `core/financeiro.py` | Separa projetado × recebido, fixo × variável | testes de cálculo |
| I13 | P3 | **Gerador de mapas** (canal 1) com Natural Earth (domínio público) | download dos dados (OK do usuário) | `core/mapas.py` | Mapa 1080×1920 com destaque e legenda de fonte | teste de render |
| I14 | P4 | Narração gerada por **clone da própria voz** (se o usuário quiser) | decisão + provedor | `core/narracao_ia.py` | Áudio marcado como gerado; nunca exporta sem revisão | teste com provedor simulado |
| I15 | P4 | Telas: "Canais e ideias", "Roteiro", "Esteira" e "Resultados" no app | I5–I12 | `web/static` | Mesmos dados da CLI; teste de interface (nome acessível, 12 px) | `test_interface` + navegador |
| I16 | P4 | Publicação via API do YouTube | OAuth + autorização explícita | — | Só com autorização configurada; nunca automática | — |

## Ordem e paradas
1. **I1–I2** (preparação) → 2. **I3–I4** (direitos e conformidade: reduzem risco já, inclusive nos projetos atuais)
→ 3. **I5–I6** (canais e ideias) → 4. **I7–I8** (roteiros e originalidade) → 5. **I9** (esteira) →
6. **I10–I12** (aprendizado e finanças) → 7. **I13** (mapas, para o canal 1) → 8. **I14–I16** conforme decisões.
Cada etapa: suíte inteira verde + documento 08 atualizado com o resultado real + commit.

## Riscos do plano
- Volume: são ~12 módulos; feitos em sequência com teste, cabem em várias sessões (o progresso fica neste
  documento e no 08).
- Dependência de decisões do usuário: Git (I1), idioma/narração (canais), download de dados (I13), OAuth (I16).
