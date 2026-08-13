# Contributing

Start with the root and project-specific `AGENTS.md` guides. Preserve the core
truth boundary: engines, human-likelihood evidence, rules, schemas, and
verifiers decide chess facts; an LLM may only phrase verified evidence.

Before opening a pull request:

```sh
./tools/prove.sh
```

API changes start in backend Pydantic/FastAPI models. Regenerate OpenAPI and
TypeScript with the commands in [`contracts/README.md`](contracts/README.md),
and commit both generated artifacts. Do not hand-edit them.

Keep changes focused, add deterministic tests for behavior, and never commit
credentials, model weights, user games, provider outputs, or local caches.
