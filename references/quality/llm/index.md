---
pack: llm
applies_when:
  project_types: [llm, agent]
  changed_globs: ["**/prompts/**", "**/agents/**", "**/*prompt*", "**/*tool*"]
  task_types: [add-tool, change-prompt, agent]
provides_rules: [LLM]
---

# LLM-app safety pack

For AI/agent codebases: prompt-injection, tool-call safety, output handling.

- [LLM](llm.md)
