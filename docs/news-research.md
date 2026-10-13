# Company news, catalysts and thesis changes

The [V2.7 continuity addendum](PRD-v2.7-Addendum-Research-Continuity.md) preserves
SQLite schema 1 and JSON input 1.0. When a disputed claim is relabeled VERIFIED without
a changed public URL, fact locator or publication date, the delta records the
label change with `UNCHANGED_CITATION_REVIEW_REQUIRED` and a supporting-evidence
warning; it is excluded from newly verified fact updates. Source-ID relabeling
or a newer access date alone is insufficient. Changed citations still require
human inspection; a schema or comparison cannot verify source truth.

The `investobot-news` skill guides an external agent through source research.
The deterministic `invest research news` commands validate supplied JSON, retain
immutable observations and compare them. Investobot does not fetch news or execute
an LLM. No API account, subscription or credential is needed for the offline MVP.
Live research requires the agent's authorized browser and permission to use each
source; manual review must verify original evidence before acceptance.

## Setup and workflow

Use the [research skills guide](research-skills.md) to install bundled guidance
explicitly into a project for Codex or Claude Code. Installation preserves modified
user files unless an explicit reviewed `--confirm` replacement is requested.
Discovery and installation do not perform research.

```sh
./scripts/invest research skills show investobot-news
./scripts/invest research news context --ticker EXAMPLE
./scripts/invest schema
./scripts/invest tools describe research.news.import
```

For an initial baseline, identify the issuer and declared monitoring window,
research original disclosures and clearly label partial or blocked coverage. For
follow-on work, review context first: stable events, catalysts, hypothesis
statements and unanswered questions. Retrieve `show` for full evidence where needed.
Check issuer/IR, filing, regulatory/legal, product/partner and independent-reporting
sources as available; disclose which categories were actually searched.

Save contract-conforming JSON under ignored `local-data`. Inspect identity, source
locators, verified/disputed claims, date certainty, implications and limitations.
Then validate and preview; obtain explicit human approval before confirmation.

```sh
./scripts/invest research news validate /app/local-data/news.json
./scripts/invest research news import /app/local-data/news.json
# Explicitly accepted by the human after reviewing the preview:
./scripts/invest research news import /app/local-data/news.json --yes
./scripts/invest research news list --ticker EXAMPLE
./scripts/invest research news show RUN_ID
./scripts/invest research news summary RUN_ID
./scripts/invest research news changes --ticker EXAMPLE
./scripts/invest research news compare RUN_OLD RUN_NEW
```

Use the generated `NewsResearchInput` schema for exact fields and enums. The fully
fictional payload in [PRD V2.7](PRD-v2.7.md#51-example-payload-entirely-fictional)
illustrates the structure; it asserts no real issuer or event. Synthetic test
results establish deterministic behavior, not real-news accuracy or legal rights.

## Evidence and identities

An `event_key` identifies one underlying development. Prefer an authoritative
announcement, filing or case identifier; otherwise reuse a manually reviewed key
supported by evidence. Different outlets repeating one disclosure belong to one
event. Identical titles can describe independent events. Never merge by headline
similarity alone; preserve ambiguity and limitations.

Stable fact keys identify checkable propositions; source IDs and exact locators
identify evidence. Only VERIFIED facts may be described as confirmed. Attribute
allegations and disputed reporting explicitly. Possible demand, revenue, margin,
cost or other business effects are agent interpretations with assumptions and
uncertainty, not reported financial facts.

Reuse catalyst IDs, question IDs and thesis IDs across observations. Catalyst
dates and changes require evidence. Hypothesis statements remain unchanged under
one thesis ID; new statements require new identities. Thesis assessments are
research judgments, not trading signals or changes to accepted investment decisions.
Comparisons require nonconflicting shared CIK/security IDs, or matching ticker
and reviewed company name when both runs lack strong IDs. Name-only continuity
is insufficient; an identical already accepted package remains a safe no-op.
Answered questions need cited evidence or an explicit closure limitation.
Set `answered_fact_key` to a VERIFIED same-event fact, or supply
`closure_limitation`; optional `evidence_needed` describes the missing evidence.
RESOLVED/RETRACTED events require `status_source_id` and
`status_source_locator`, referencing a cited event source. Summary and changes
retain these exact outcome locators alongside before/after source links.

Actual event dates differ from source publication dates, source access dates and
import timestamps. Unknown dates remain unknown. Future catalysts may have future
dates. The research window covers publication/discovery, not a guarantee that all
events occurred within it; an older story found now is newly observed, not newly
occurred. Coverage within a declared scope never means universal news coverage.

## Reading deltas and preserving history

Comparisons use stable identities and explicit before/after evidence. Added
sources supporting unchanged facts are corroboration; headline edits and reordered
arrays are not material developments. New verified facts can update an existing
story. Source disputes and incompatible hypotheses remain visible.

Missing events are `not_reobserved`, never automatically closed, resolved,
dismissed or disproven. Missing catalysts have not necessarily occurred or been
cancelled. Partial coverage and empty arrays do not establish no news. Review
unanswered questions and nonoverlapping windows before interpreting any delta.

### Effective context across research gaps

`context --ticker TICKER` names the latest accepted baseline, ordered by
`researched_as_of`, then `imported_at`, then run ID. It reconstructs compact
context from compatible same-company history using relational projections,
without reading full packages or changing the ledger. Its baseline metadata,
coverage window, limitations and warnings still describe the latest run.

Each carried record adds `last_observed_run_id`, `last_observed_as_of` and
`observation_status`: `OBSERVED_IN_BASELINE` or `NOT_REOBSERVED`. Source
provenance identifies its originating run because source IDs are run-scoped.
These fields mark recorded knowledge, not proof that an issue remains ongoing
today. Recheck older evidence explicitly and retain unknown occurrence dates.

For example, fictional Run A records a developing lawsuit and an open question;
Run B omits both. Context before Run C still includes them as `NOT_REOBSERVED`,
last observed in A. Pending catalysts and tracked hypotheses also survive
omissions. An inherited thesis adds `reassessment_status: NOT_REASSESSED`; silence
does not reject it. No automatic expiry applies, even if B declared complete
coverage. The most recent actual observation governs each stable key, so carried
records are not duplicated. Explicit sourced resolution or retraction stops
active event carry-forward; historical runs remain retrievable with `show`.

### Reobservations and disputed claims

`compare` and `changes` add `reobserved_events` and `disputed_claim_changes`, with
matching entries in `counts`. All existing arrays and counts remain available;
missing-baseline responses include the new arrays as empty and their counts as
zero. These are additive read-output changes; JSON input remains v1.0; the current SQLite
schema is 1. The bundled news skill is v1.0.1; earnings and political skills
retain their versions.

If C observes A's stable event again after B omitted it, B-versus-C reports
`reobserved_events`, with A's last observation, C's record and before/after
evidence. Any new verified facts are still visible; the event is not newly
discovered. Explicit comparisons search compatible history only at or before
their selected old baseline in research order, preventing future observations
from leaking into earlier comparisons. Ambiguous issuers and title similarity
never establish continuity.

Disputed claims are reported separately by event and fact key:

| Change | Interpretation |
| --- | --- |
| `DISPUTED_ADDED` | A newly recorded allegation, not a verified company fact. |
| `DISPUTED_REVISED` | The checkable disputed proposition changed materially. |
| `DISPUTED_TO_VERIFIED` | The proposition is now verified with supporting evidence. |
| `VERIFIED_TO_DISPUTED` | Confirmed-fact treatment is withdrawn; falsity is not established. |
| `DISPUTED_NOT_REOBSERVED` | Missing coverage, not withdrawal, resolution or disproof. |

Each entry includes before/after facts as applicable, run IDs, source URLs,
locators and an uncertainty caveat. Additional corroboration of an unchanged
claim is evidence-only; whitespace, ordering, source-ID relabeling and headline
edits alone are not material changes. A dispute becoming verified may also
appear under `updated_events`; counts describe categories and must not be summed
as distinct business developments. Humans assess significance after reviewing
the evidence; disputed claims are research leads, never trading signals.

Accepted runs are immutable, atomic and idempotent. Research changes no holdings,
prices, classifications, lots, targets, market caches or plan freshness.
Fresh checksum-identified SQLite schema 1 initializes through existing application
behavior. Use disposable synthetic ledgers for evaluation; see
[operations](operations.md).

Store source metadata and concise independently authored facts, not full articles
or raw pages. Respect copyright and source usage restrictions, strip credentials
and tokens, retain safe public locators, and omit unsolicited personal information.
No scheduled polling, alerts, scraping or automated investment action is included.
