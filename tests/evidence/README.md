# Unified MVP red evidence

`unified-mvp-red.json` records observed executable scenario outcomes before
production changes. The original baseline at
`5120897e9e5a314ad50fb242ad1496d976549a92` passed 862 tests and explicit-config
Ruff in offline Docker. New inputs are fictional and source-dated.

A red outcome is an unmet requirement, not a release-ready result. Passing old
regressions do not demonstrate new capabilities. Full acceptance includes the
entire preserved suite, new scenarios, locked offline packaging, recovery and
manual source/provider gates. The test-only red commit is recorded in the
implementation evidence document after committing; no self-referential commit
hash is required in this file.
