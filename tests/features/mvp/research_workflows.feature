Feature: Honest research coverage and portable agent workflows

  Scenario: B49 Partial issuer research preserves exposure coverage
    Given a frozen synthetic twenty issuer research batch
    When portfolio research is summarized
    Then twelve researched issuers cover sixty percent with eight not researched

  Scenario: B50 Syndicated evidence is one development
    Given two sources cite the same synthetic issuer event
    When portfolio research is summarized
    Then one development retains both source citations

  Scenario: B51 Political categories remain distinct
    Given sourced executive and corporate PAC evidence
    When portfolio research is summarized
    Then political categories remain separate without stance scores

  Scenario: B52 Human approval cannot override contributor permissions
    Given named contributor evidence lacks reviewed permission
    When portfolio research is summarized
    Then named contributions are excluded with explicit permission diagnostics

  Scenario Outline: <id> Installed workflow drives discoverable real commands
    Given the synthetic <workflow> workflow intent
    When its installed skill is followed by a scripted CLI driver
    Then the <workflow> workflow obeys its boundary and reports its outcome
    Examples:
      | id  | workflow    |
      | B53 | sync        |
      | B54 | performance |
      | B55 | monthly     |
      | B56 | harvest     |
      | B57 | screening   |
      | B58 | research    |
      | B59 | strategy    |

  Scenario: B60 Tool descriptors match executable flags and schema
    Given a registered portfolio performance command
    When its descriptor and executable help are read
    Then flags schema mutation scope and structured result agree

  Scenario: B61 Offline keyword retrieval returns cited permitted text
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When keyword research retrieval runs without embeddings
    Then cited permitted matching passages are returned without network access

  Scenario: B62 Semantic retrieval rejects incompatible model dimensions
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When incompatible semantic queries are submitted
    Then both model and dimension mismatches are explicit and text retrieval still works

  Scenario: B63 Derived vector rebuild preserves canonical data
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When the derived vector index is dropped rebuilt and searched
    Then canonical vectors documents and financial rows stay identical and retrieval returns

  Scenario: B64 Permissions filter both retrieval methods
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When matching text and compatible vectors are queried
    Then forbidden evidence is absent from both retrieval methods

  Scenario: R01 Research previews and accepted repeats preserve actual financial state
    Given a real accepted synthetic household and a cited research envelope
    When research is previewed and explicitly accepted twice
    Then preview writes nothing repeat is a no-op and financial state is identical

  Scenario: R02 Invalid research batch acceptance is atomic
    Given a real accepted synthetic household and a cited research envelope
    When a batch contains a conflicting evidence identity
    Then the batch is rejected without partial research or financial changes

  Scenario: R03 Unverified PAC relationship remains excluded
    Given sourced executive and corporate PAC evidence
    And the issuer PAC relationship is unverified
    When portfolio research is summarized
    Then only executive contributions are counted and PAC relationship is unresolved

  Scenario: R04 Research aggregate retains disputed and missing events
    Given dated research with disputed and not reobserved developments
    When portfolio research is summarized
    Then occurrence publication dates and unresolved event statuses remain distinct

  Scenario: S01 Chunk content and embedding model revisions are immutable
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When source text and embedding model are explicitly revised
    Then prior chunks and vectors remain unchanged with distinct revision provenance

  Scenario Outline: S02 Invalid vectors are rejected atomically
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When a <kind> vector is submitted
    Then invalid vectors cannot mutate canonical corpus or financial state
    Examples:
      | kind       |
      | zero       |
      | nonfinite  |
      | nonunit    |
      | empty      |

  Scenario: S03 Text filters and hybrid scores are reproducible
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When issuer date and top-k constrained searches are repeated
    Then filters apply before ranking and hybrid components have stable ties

  Scenario: S04 Missing vector index preserves offline text access
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When the real derived vector index is removed without rebuilding
    Then semantic availability is explicit and keyword retrieval remains cited

  Scenario: S06 Personal contribution and brokerage documents are not implicitly indexed
    Given a synthetic SQLite corpus with permitted and forbidden passages
    When private broker and named contributor documents are submitted without indexing rights
    Then private chunks are rejected atomically and absent from retrieval

  Scenario Outline: W01 Full portable <workflow> walkthrough in <mode> state
    Given the complete synthetic <workflow> walkthrough with <mode> inputs
    When the portable skill documented command sequence is scripted
    Then the complete <workflow> sequence preserves its <mode> authorization boundary
    Examples:
      | workflow    | mode    |
      | sync        | success |
      | sync        | blocked |
      | performance | success |
      | performance | blocked |
      | monthly     | success |
      | monthly     | blocked |
      | harvest     | success |
      | harvest     | blocked |
      | screening   | success |
      | screening   | blocked |
      | research    | success |
      | research    | blocked |
      | strategy    | success |
      | strategy    | blocked |

  Scenario: R05 Frozen research universe preserves household denominator and source coverage
    Given a sourced single currency lookthrough universe with unresolved exposure
    When the company universe is frozen into an issuer research manifest
    Then issuer weights use whole household value and keep identity source and missing coverage
