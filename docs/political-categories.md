# Political contribution categories

Political research accepts three explicit package types:

- `EXECUTIVE_POLITICAL_CONTRIBUTIONS`: existing executive interchange remains
  compatible; omitted contribution category means executive personal evidence.
- `EMPLOYEE_POLITICAL_CONTRIBUTIONS`: every contribution declares
  `contributor_category: EMPLOYEE_PERSONAL`.
- `CORPORATE_PAC_POLITICAL_CONTRIBUTIONS`: every contribution declares
  `contributor_category: CORPORATE_PAC` and reviewed corporate PAC linkage.

The existing `executives` collection and `executive_id` reference are retained
as the interchange's contributor identity fields. They do not turn an employee
or committee into an executive. Category and research type remain in the
immutable original package; totals must retain these separate categories.

Corporate PAC `corporate_pac_identity_evidence` contains the exact committee ID
(`C` plus eight digits), company and registration source IDs, a narrow original
source locator, and `reviewed: true`. Both distinct sources must be cited by the
contribution. The company source must be the contributor's role source and have
source type `CORPORATE_PAC_REGISTRATION`. Personal contributions cannot carry
this linkage. Structural acceptance checks references and recorded review; it
cannot establish that the original evidence is true.

Human setup remains mandatory: review the original identity evidence and source
rights for investment research, then save a local reviewed rights policy and
select it with `INVEST_RESEARCH_POLICY` (or the public import's `policy_path`).
An agent's `rights_basis`, package `APPROVED`, or import confirmation alone does
not authorize use. Named employee and executive evidence requires independently
permitted source origins, including separate FEC-derived permission when
applicable. Corporate PAC imports retain the same conservative reviewed policy
gate for contribution disclosure sources; this is not a legal finding that
committee evidence is personal data. No source pages or private donor fields
are stored. Synthetic fixtures require no external accounts or secrets.

Acceptance writes only immutable research. It does not register issuers, update
holdings, place trades, score political alignment, or certify legal permissions.
