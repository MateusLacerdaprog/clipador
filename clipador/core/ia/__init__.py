"""Camada de IA independente de fornecedor (Claude, OpenAI, Gemini, Ollama local).

Regras: chaves so no cofre do Windows (keyring) ou em variavel de ambiente, nunca no navegador, em logs ou no
projeto; nenhum video/audio e enviado (so texto); o usuario ve o que sera enviado e precisa consentir por
provedor; se a IA falhar, a edicao manual continua funcionando.
"""
