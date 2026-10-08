# Development evidence
All tests and dependency tools run in Docker. Conventional red/green commits track feature work. Synthetic BDD fixtures need no credentials or internet.

Foundation: observed3 missing-ledger failures before implementation; green3. Import consistency:1 expected failure and5 existing-behavior regression passes; green9. Tax/market/inspection: modules absent before implementation; full suite42 green. Exposure/normalization/bonds: expected4+2+4 failures; full suite52 green.

A parallel tax audit wrote new scenarios between the52-test run and the following commit, so that commit also contains red tests. The coordinator then observed3 expected audit failures (retained-share quantity, missing estimate assumptions, unknown tax status); production was unchanged until this red evidence commit. The passing mixed-loss/net-gain audit scenario verifies behavior already implemented. Coordinate test writes at commit boundaries to avoid this race.

Scenario/risk:7 missing-behavior failures observed, full64 green after implementation. Discovery:6 expected missing-module failures; inspection analysis:3 expected missing-endpoint failures; identity/basis/cash/history hardening:4 failures. Full80 green after integration, including3 composite acceptance scenarios. Composite acceptance scenarios intentionally exercise existing functionality and passed without new domain code; they are integration regression evidence rather than new implementation chunks.
