# 08 — Testes e validação (Fase 9)

**Execução real em 18/10/2026:** `python -m pytest tests -q` → **259 passed in 524.45 s (8 min 44 s)**, sem falhas
(estado inicial do projeto: 233). Ciclo rápido `-m "not lento"`: 203 passed (≈ 2 min). Ambiente: Windows 11,
Python 3.13.15, FFmpeg no PATH, dependências do `requirements.txt`.

## Testes novos deste projeto (26)

| Arquivo | Teste (o que prova) | Resultado | Evidência |
|---|---|---|---|
| test_qualidade.py | todo import externo está no `requirements.txt` | ✅ | suíte |
| test_recursos.py (5) | validação de origem/licença (licença obrigatória, link só http, origem inválida); projeto antigo migra como "não informado" e registrar licença **não** derruba a aprovação; rotas de direitos da fonte e da biblioteca (400/404, `_direitos.json` não vira música); tempo da montagem por origem | ✅ | suíte |
| test_conformidade.py (5) | termos de risco no título/gancho/legenda dos 7 s (e não depois); terceiros sem narração (F1), Short > 60 s sem licença (F3), música sem licença (F8/F3), duplicado só contra projeto exportado (F5); itens entram no Verificar com a regra | ✅ | suíte |
| test_estudio.py (8) | canais (validação, semear sem duplicar, GTA "sem_receita"); pontuação CPV (pesos = 100, portão reprova antes da nota, bool não vale como nota, aprovar exige fonte); roteiro (só de ideia aprovada, bloqueios, recompensa cedo, versões, reaprovação após editar, termo de risco no gancho); roteiro parecido só no mesmo canal; sugestão da IA **não entra sem aplicar** e fonte inventada vira "a confirmar"; roteiro aprovado vira projeto; limite diário do canal; rotas e erros 400/404/409; CLI | ✅ | suíte |
| test_esteira_resultados.py (7) | etapas deduzidas do estado real (retoma da primeira pendente); publicação só com link válido + FINAL; trava contra execução duplicada (e trava velha ignorada); CSV do Studio em inglês e português (sinônimos, coluna desconhecida preservada, linha "Total" ignorada, "0:00:31" → 31 s, vírgula decimal); experimento inconclusivo com amostra pequena e "B acima de A" com IC > 0; finanças (custo de IA só conhecido, lucro realizado só com receita importada, projeção exige parâmetros) | ✅ | suíte |

Cobertura dos itens mínimos pedidos: criação/edição de projetos ✅ (suítes existentes + roteiro→projeto) · geração
de roteiros ✅ (esqueleto, checagem, IA simulada) · rastreabilidade de fontes ✅ · música + narração sobrepostas ✅
(suíte de áudio existente) · controle do áudio original ✅ (existente) · legendas e sincronia ✅ (existente) ·
exportação vertical ✅ (existente, render real) · recuperação de falhas ✅ (esteira retoma; render .tmp + ffprobe
existente) · recursos e licenças ✅ · proteção de credenciais ✅ (testes de IA com cofre de teste, existentes) ·
conformidade ✅ · persistência ✅ · publicação: só o **registro** do link (publicação automática não existe).

## Falhas encontradas pelos testes e corrigidas

| Falha | Como apareceu | Correção |
|---|---|---|
| "VAZOU" não era pego como termo enganoso (só "vazado/vazada") | test_estudio | regex com as formas do verbo (vazou, vazaram, vazamento) |
| Duas importações de CSV no mesmo segundo empatavam; o "último" retrato vinha em ordem aleatória | test_esteira_resultados | carimbo `ordem` em nanossegundos para desempatar |
| Resumo "sem problemas" ia para o fim da lista quando havia dicas | test_retencao (existente) | o resumo abre a lista, como na publicação |
| `requirements` / imports | — | sem falha (teste novo passou de primeira) |

## Não testado / bloqueado (com instrução reproduzível)

| Item | Motivo | Como testar |
|---|---|---|
| Importar um CSV **real** do YouTube Studio | não há export do canal do usuário | Studio → Análises → Modo avançado → Exportar CSV → `python -m clipador metricas importar "Table data.csv"`; conferir a lista de "colunas não reconhecidas" |
| Sugestão de roteiro com provedor de IA **real** | testes usam provedor simulado (sem gastar e sem chave) | configurar o provedor em "Provedores de IA", aceitar o consentimento e chamar `POST /api/roteiros/<id>/ia` |
| Telas do estúdio no navegador | ainda não existem (I15) | — |
| Publicação via API do YouTube | não implementada (opcional, exige OAuth e autorização) | — |
| Dublagem automática PT→EN em Shorts | a página oficial não diz se vale para Shorts | publicar um vídeo longo e checar a aba Idiomas no Studio |
