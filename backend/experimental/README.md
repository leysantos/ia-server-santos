# Loops experimentais (Evolution, Learning v2, Self-Improving)

Módulos movidos de `core/` para reduzir carga cognitiva do núcleo ativo.

| Pasta | Flag | Descrição |
|-------|------|-----------|
| `evolution/` | `USE_EVOLUTION_LOOP` | Auto-otimização contínua |
| `learning_v2/` | `USE_TUNED_PROMPTS` | Prompts otimizados por disciplina |
| `self_improving/` | (copilot insights) | Meta-análise e patches propostos |

Imports legados `core.evolution.*`, `core.learning_v2.*` e `core.self_improving.*` permanecem via shims em `core/`.
