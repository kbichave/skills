# LLM — AI-app safety

### LLM-001: Isolate untrusted content in prompts
- **Trigger:** injecting external/user/tool content into a prompt.
- **Required behavior:** delimit and label untrusted content; never let it override system instructions; treat tool output as data, not instructions.
- **Verification signal:** reviewer; injection test case.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### LLM-002: Tool-call allowlisting + argument validation
- **Trigger:** exposing tools/functions to a model.
- **Required behavior:** explicit allowlist; validate/authorize arguments before execution; no arbitrary command/path/SQL from model output.
- **Verification signal:** reviewer; test for disallowed tool/args.
- **Severity:** BLOCK
- **Enforcer:** reviewer + test

### LLM-003: Sanitize/contain model output
- **Trigger:** using model output in downstream sinks (HTML, shell, SQL, files).
- **Required behavior:** treat output as untrusted; escape/validate at the sink.
- **Verification signal:** reviewer.
- **Severity:** BLOCK
- **Enforcer:** reviewer

### LLM-004: Bound cost/loops
- **Trigger:** agent loops / recursive tool calls.
- **Required behavior:** max-iteration and token/time budgets enforced.
- **Verification signal:** reviewer; test.
- **Severity:** WARN
- **Enforcer:** reviewer
