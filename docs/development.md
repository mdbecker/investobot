# Development evidence
All tests and dependency tools run in Docker. Conventional red/green commits track feature work. Synthetic BDD fixtures need no credentials or internet.

Foundation: observed3 missing-ledger failures before implementation; green3. Import consistency:1 expected failure and5 existing-behavior regression passes; green9. Tax/market/inspection: modules absent before implementation; full suite42 green. Exposure/normalization/bonds: expected4+2+4 failures; full suite52 green.

A parallel tax audit wrote new scenarios between the52-test run and the following commit, so that commit also contains red tests. The coordinator then observed3 expected audit failures (retained-share quantity, missing estimate assumptions, unknown tax status); production was unchanged until this red evidence commit. The passing mixed-loss/net-gain audit scenario verifies behavior already implemented. Coordinate test writes at commit boundaries to avoid this race.

Scenario/risk:7 missing-behavior failures observed, full64 green after implementation. Discovery:6 expected missing-module failures; inspection analysis:3 expected missing-endpoint failures; identity/basis/cash/history hardening:4 failures. Full80 green after integration, including3 composite acceptance scenarios. Composite acceptance scenarios intentionally exercise existing functionality and passed without new domain code; they are integration regression evidence rather than new implementation chunks.

Final data hardening:2 exposure/currency and2 quote TTL failures observed before changes; full84 green. Inspection inconsistent-state response:1 expected disconnected-response failure observed and committed before error handling; full85 green plus Ruff checks and locked Docker rebuild. No live FMP credentials were used; institution HTML support remains provisional until samples arrive.

Deployment verification exposed a Docker Desktop nested-mount interaction when cleaning the workspace dependency directory. Added an observed failing runtime-location BDD scenario, then moved dependencies to /opt/venv outside the bind mount. Full86 tests and Ruff passed; the rebuilt running container's `invest portfolio summary` entry point and localhost HTTP response were checked. The repository contains no host virtual environment.
