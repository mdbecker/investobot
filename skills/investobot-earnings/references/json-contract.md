# Authoritative contract and CLI

Inspect `EarningsResearchInput` through `invest schema` and use
`invest tools describe research.earnings.validate` and
`invest tools describe research.earnings.import` for current input contracts.
Do not duplicate schemas in skill text. Return one valid JSON object without
Markdown fences, with exact decimal strings and original source identifiers.

The package distinguishes company identity, research/reporting scope, sources,
historical financial metrics, guidance, findings and limitations. Preserve
unresolved issues in limitations as supported by the contract. The research
type is `EARNINGS_FINANCIAL_STATEMENTS`; contract version is `1.0`.
Investobot supplies trusted bundled skill metadata independently of the agent.
Use the supported schema's field names and enum values rather than inventing
period labels or missing measurements.

```sh
invest research earnings validate /app/local-data/earnings.json
invest research earnings import /app/local-data/earnings.json
invest research earnings import /app/local-data/earnings.json --yes
invest research earnings list --ticker EXAMPLE
invest research earnings show RUN_ID
invest research earnings summary RUN_ID
invest research earnings compare RUN_A RUN_B
```

Preview and validation are read-only. Explicit acceptance stores immutable
research only, with no change to household financial facts or market observations.
Identical normalized packages are idempotent. List is compact; show retrieves
complete evidence. Comparisons require genuinely compatible saved observations.
## 8.1 Example JSON

All company and financial values below are fictional.

```json
{
  "schema_version": "1.0",
  "research_type": "EARNINGS_FINANCIAL_STATEMENTS",
  "company": {
    "name": "Fictional Technology Corporation",
    "ticker": "FAKE",
    "cik": "0000000001",
    "security_id": null
  },
  "reporting_period": {
    "fiscal_year": 2026,
    "fiscal_period": "Q2",
    "period_end": "2026-06-30"
  },
  "researched_as_of": "2026-10-10",
  "coverage_status": "PARTIAL",
  "sources": [
    {
      "id": "source-10q",
      "source_type": "SEC_10_Q",
      "url": "https://example.invalid/fictional-filing",
      "accession_number": "SYNTHETIC-ACCESSION",
      "filed_at": "2026-08-01",
      "accessed_at": "2026-10-10",
      "publisher": "Fictional Technology Corporation"
    }
  ],
  "metrics": [
    {
      "id": "revenue-q2",
      "metric_code": "REVENUE",
      "metric_label": "Consolidated revenue",
      "value": "1250000000.00",
      "unit": "USD",
      "accounting_basis": "GAAP",
      "measurement_type": "REPORTED",
      "period_type": "DURATION",
      "period_start": "2026-04-01",
      "period_end": "2026-06-30",
      "fiscal_year": 2026,
      "fiscal_period": "Q2",
      "scope": "CONSOLIDATED",
      "segment_name": null,
      "source_id": "source-10q",
      "source_locator": "Financial statements; consolidated revenue",
      "xbrl_taxonomy": null,
      "xbrl_concept": null
    }
  ],
  "guidance": [],
  "findings": [
    {
      "id": "finding-1",
      "category": "MANAGEMENT_EXPLANATION",
      "statement": "Fictional example: management attributed growth to higher demand.",
      "source_id": "source-10q",
      "source_locator": "Management discussion",
      "limitations": []
    }
  ],
  "limitations": [
    "Synthetic example; no real financial disclosure was reviewed.",
    "Only one reporting metric is represented."
  ]
}
```

