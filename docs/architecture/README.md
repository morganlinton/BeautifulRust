# Architecture diagrams

Interactive Archify diagrams for the Rust backend stack this set teaches:
axum 0.8 + tokio + sqlx on Postgres 17, laid out as a hexagonal crate
workspace (core → ports → slices → composition root) with vertical slicing,
a zero-broker `email_jobs` outbox and a JWT/argon2 identity stack.
Each diagram is a standalone HTML page (open it in any browser); the JSON next
to it is the source. Naming follows the backend-rust template convention:
`c4-containers` ships without a type infix, every other stem carries
`<stem>.<type>`.

| Diagram | Type | What it shows | Source | Rendered |
|---|---|---|---|---|
| c4-containers | architecture | Containers: SPA/SDK clients, edge nginx, axum API, PostgreSQL 17, outbox worker (loom bin), OIDC IdP, mail + OTLP vendors | [json](c4-containers.json) | [html](c4-containers.html) |
| services-slices | architecture | The crate map: composition root → slices (auth · widgets) → ports (traits + Pg adapters) → core, with warden, mailer, loom and the `email_jobs` outbox | [json](services-slices.architecture.json) | [html](services-slices.architecture.html) |
| outbox-algorithm | workflow | Durable task delivery: transactional INSERT into `email_jobs`, claim CTE (SKIP LOCKED · 5-minute lease), render, deliver, 2^n backoff and dead-letter | [json](outbox-algorithm.workflow.json) | [html](outbox-algorithm.workflow.html) |
| auth-sequence | sequence | Signup-to-login trace: one sqlx transaction for user + code + job, outbox claim, code delivery, verify, then gates and token mint with rotating refresh | [json](auth-sequence.sequence.json) | [html](auth-sequence.sequence.html) |
| outbox-sequence | sequence | Producer/worker/vendor trace for one queued email: commit, claim, send, `mark_sent`, retry and dead-letter, then the hourly janitor sweep | [json](outbox-sequence.sequence.json) | [html](outbox-sequence.sequence.html) |
| database-dataflow | dataflow | Identity + outbox data flow across clients → use-cases → Postgres state and code tables → `email_jobs` → mail delivery, with transactional enqueue and retry edges | [json](database-dataflow.dataflow.json) | [html](database-dataflow.dataflow.html) |
| runtime-lifecycle | lifecycle | Runtime states from boot: typed-env validation, AppState wiring with embedded migrations, axum serve, readyz gate, request flow, outbox drain, 503-degraded and exit-1 endings | [json](runtime-lifecycle.lifecycle.json) | [html](runtime-lifecycle.lifecycle.html) |

| auth-algorithm | workflow | Signup algorithm: credentials, same-tx outbox enqueue of the verification email, 5-try code gate, login gates, token mint with audit | [json](auth-algorithm.workflow.json) | [html](auth-algorithm.workflow.html) |
