# Research method

Confirm the legal reporting entity, ticker/share class, corporate relationships
and SEC CIK where available. A similarly named issuer is not sufficient evidence.
Identify the requested quarter/year and issuer fiscal calendar before extraction.

Prefer original SEC 10-Q/10-K filings and amendments, issuer earnings releases,
investor-relations presentations and sourced management guidance. SEC XBRL and
Company Facts can aid discovery but omit custom disclosures or segment dimensions.
Consult the original filing for those omissions and conflicts.

Retain source URL, publisher, filing/accession reference, disclosed publication
date and research retrieval date. Preserve source locators precise enough to
verify each metric. For XBRL observations retain available taxonomy, concept,
unit, reporting duration/instant, filing accession and fiscal context. Do not
select a value solely because it was the most recently retrieved response.

Extract exact disclosed metrics with period, basis and scope. Record guidance
separately with future period and sourced bounds. Label disclosed facts and agent
interpretations distinctly. Preserve unresolved conflicts and missing information;
no invented zero, missing currency, fiscal period or reconciliation.

Verify each observation against its original disclosure before handing JSON to
Investobot. Pydantic cannot prove that a cited document supports a claim. Do not
silently combine similarly named metrics with different definitions or scopes.

Save JSON in ignored local-data. Validate and preview with the deterministic CLI,
then present evidence and limitations for explicit acceptance. A revised period
or filing becomes a new run, preserving the earlier evidence. No account/API key
is needed for fictional offline verification; live original-source review remains
a separate activity. Respect project Docker-only execution requirements.
