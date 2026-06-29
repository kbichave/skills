# PERF — Performance

All PERF rules are **evidence-gated**: emit only with a measured number, never on
suspicion (decision: AI reviewers hallucinate perf issues otherwise).

### PERF-001: No premature optimization
- **Trigger:** added complexity justified by speed.
- **Required behavior:** optimize only with a measurement showing need.
- **Verification signal:** reviewer cites a benchmark.
- **Severity:** ADVISE
- **Enforcer:** reviewer

### PERF-002: Bounded memory/IO
- **Trigger:** loading collections/files.
- **Required behavior:** stream/paginate; no unbounded loads of user-scaled data.
- **Verification signal:** reviewer cites the unbounded read.
- **Severity:** WARN
- **Enforcer:** reviewer

### PERF-003: Cache has invalidation + TTL
- **Trigger:** adding a cache.
- **Required behavior:** explicit invalidation strategy and TTL.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer

### PERF-004: Pagination on large reads
- **Trigger:** reading a large dataset.
- **Required behavior:** paginate.
- **Verification signal:** reviewer.
- **Severity:** WARN
- **Enforcer:** reviewer
