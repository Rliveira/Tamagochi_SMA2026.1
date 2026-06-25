# Tamagochi_SMA2026.1
Projeto da Disciplina de Sistemas Multiagentes, ministrada pelo professor Pablo Sampaio na Universidade Federal Rural de Pernambuco. Alunos: Rony Elias e João Victor

## Arquitetura de IA
O projeto está organizado em três camadas: `engine_biologia.py` controla o estado fisiológico e a Behavior Tree reativa do pet; `agente_llm.py` usa uma Behavior Tree cognitiva para escolher a estratégia de comportamento, limitar ferramentas e orientar o LLM; `main_ui.py` apenas renderiza sprites, HUD e interações do usuário.

Essa separação mantém o blackboard compartilhado como ponto de integração e deixa explícito o papel de cada módulo na arquitetura do projeto
.
