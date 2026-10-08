# MVP PRD — Local Tax-Aware Investment Copilot Tooling

## 1. Product Summary

Build a small local Python toolkit that gives an existing browser-equipped AI agent reliable financial capabilities it cannot safely or efficiently perform through Chrome alone.

The agent already handles:

- current news research;
- qualitative company/fund research;
- SEC and investor-relations browsing;
- macro and industry research;
- discovering possible securities;
- reading public websites;
- open-ended investment discussion.

The MVP therefore focuses only on capabilities where browser-only agents are weak:

1. exact persistent portfolio state;
2. deterministic account and HTML reconciliation;
3. tax-lot and wash-sale analysis;
4. complete ETF/mutual-fund holdings comparison;
5. household look-through exposure;
6. historical quantitative analysis;
7. hypothetical portfolio/trade simulation;
8. structured security screening and replacement discovery;
9. deterministic fixed-income calculations.

The system never places trades.

The human executes all trades manually. The toolkit only records portfolio state, performs calculations, proposes scenarios, and reconciles subsequent portfolio snapshots.

The existing agent invokes tools through the CLI and uses Chrome independently when qualitative or current public-web research is appropriate.

---

# 2. Product Principles

## 2.1 KISS

The MVP must remain a single local Python application.

Do not introduce:

- microservices;
- message queues;
- containers as a runtime requirement;
- vector databases;
- workflow engines;
- broker APIs;
- Plaid or account aggregators;
- MCP;
- LLM SDKs;
- automatic trading;
- browser automation inside this project;
- multiple market-data vendors unless strictly necessary;
- plugin systems;
- complex ORM frameworks.

The existing external AI agent is the orchestrator.

This repository only provides deterministic CLI tools.

## 2.2 Human execution is mandatory

The application must never possess brokerage trading credentials or submit orders.

The workflow is:

```text
Account HTML / manual activity
        ↓
Local canonical ledger
        ↓
Deterministic analysis
        ↓
Agent research + discussion
        ↓
Proposed trade/scenario
        ↓
Human manually executes
        ↓
Human records trade OR imports next account snapshot
        ↓
Ledger reconciliation
```

## 2.3 Browser-first research

Do not implement a dedicated feature when a frontier browser agent can already perform it well.

Chrome remains the preferred mechanism for:

- recent news;
- investment theses;
- company developments;
- analyst commentary;
- SEC filing interpretation;
- earnings-call research;
- macroeconomic research;
- management commentary;
- public fund documentation;
- discovering candidate investments.

CLI tools exist when correctness, persistence, exhaustive datasets, normalization, or repeatable calculation matters.

---

# 3. User

Primary user:

A technically sophisticated individual managing multiple taxable and tax-advantaged investment accounts who wants an AI-assisted portfolio copilot without permitting AI-directed trade execution.

Expected account types include:

- taxable brokerage;
- Traditional IRA;
- Roth IRA;
- 401(k);
- HSA;
- other retirement/tax-advantaged accounts;
- cash/bank accounts.

Expected securities include:

- common stocks;
- ETFs;
- mutual funds;
- Treasury securities;
- corporate/municipal/agency bonds;
- cash and cash equivalents.

Options and other derivatives are explicitly out of scope for MVP portfolio optimization.

They may still be stored as unsupported holdings if encountered during import.

---

# 4. Core Product Decisions

These decisions are final for MVP.

## Runtime and packaging

Use:

- Python 3.12+;
- `uv` for dependency management and locking;
- `Typer` for the CLI;
- `Pydantic` for input/output validation;
- Python `sqlite3` for persistence;
- `Decimal` for monetary values and quantities where precision matters;
- Pandas plus BeautifulSoup/lxml for HTML/tabular parsing;
- NumPy/SciPy/Pandas for quantitative calculations;
- QuantLib for fixed-income calculations;
- pytest + pytest-bdd for testing;
- Ruff for formatting/linting.

Do not use SQLAlchemy or an ORM.

Schema changes use a small explicit migration module and an integer schema version stored in SQLite.

## CLI structure

Expose one executable:

```text
invest
```

Do not create dozens of unrelated Python executables.

Use subcommands.

Examples:

```text
invest portfolio import
invest portfolio summary
invest tax analyze
invest fund compare
invest portfolio exposure
invest portfolio simulate
```

Every successful command emits machine-readable JSON to stdout.

Diagnostics and errors go to stderr.

Exit code:

```text
0 = success
1 = invalid user input
2 = external data unavailable
3 = inconsistent portfolio state
4 = internal error
```

## Persistence

Default database:

```text
~/.local/share/invest-copilot/portfolio.db
```

Use `platformdirs` so the location works correctly across supported operating systems.

Configuration:

```text
~/.config/invest-copilot/config.toml
```

## Raw account HTML

Raw brokerage/bank HTML must not be persisted.

The importer may read:

```text
file
stdin
```

After parsing, store only:

- normalized snapshot;
- source institution/profile;
- import timestamp;
- source timestamp if identifiable;
- SHA-256 hash of input;
- warnings.

This reduces accidental storage of account numbers or other sensitive page contents.

## Market-data vendor

Use **Financial Modeling Prep (FMP)** as the sole paid/general-purpose structured market-data provider for MVP.

It supplies the structured data required for:

- prices;
- historical prices;
- fundamentals used by screening;
- security metadata;
- ETF/mutual-fund metadata;
- ETF/mutual-fund holdings where available.

Do not integrate a second commercial market-data provider in MVP.

Public browser research remains the fallback for facts not available from structured tools.

## Other external sources

Use narrowly scoped free sources only where appropriate:

- OpenFIGI for identifier normalization when required;
- U.S. Treasury/FRED for rate or macro series required by calculations.

Do not build SEC/news APIs in MVP because the browser-equipped agent already handles these tasks well.

## Data freshness

Every externally retrieved result must include:

```text
source
retrieved_at
data_as_of
```

when the upstream source supplies an as-of timestamp.

Never silently present stale cached data as current.

---

# 5. Canonical Data Model

The SQLite ledger is authoritative for user-specific state.

Minimum entities:

```text
accounts
securities
positions
lots
cash_balances
activities
snapshots
market_data_cache
fund_holdings_cache
trade_proposals
```

## Account

Required fields:

```text
id
name
institution
account_type
tax_status
currency
active
```

`tax_status` is one of:

```text
TAXABLE
TAX_DEFERRED
TAX_FREE
OTHER
```

Examples:

```text
Traditional IRA → TAX_DEFERRED
401(k)          → TAX_DEFERRED
Roth IRA        → TAX_FREE
Taxable broker  → TAXABLE
```

## Security

Do not use ticker as identity.

Required canonical identifier:

```text
internal UUID
```

Store available aliases:

```text
ticker
CUSIP
ISIN
FIGI
security name
asset type
currency
```

Supported asset types:

```text
STOCK
ETF
MUTUAL_FUND
TREASURY
BOND
CASH
OTHER
```

## Position

A position is a snapshot-level quantity.

Required:

```text
account
security
quantity
market_value
price if available
as_of
```

## Lot

Required when source data supplies lot information:

```text
account
security
acquisition_date
quantity
remaining_quantity
cost_basis
```

If lot detail is unavailable, do not fabricate it.

Return an explicit capability warning.

## Activity

Supported MVP activity types:

```text
BUY
SELL
TRANSFER_IN
TRANSFER_OUT
DIVIDEND
INTEREST
FEE
CASH_DEPOSIT
CASH_WITHDRAWAL
```

Activities may be imported or manually recorded.

---

# 6. Tool Surface

The MVP exposes the following user/agent-facing command groups.

---

## 6.1 Portfolio Import and Reconciliation

Commands:

```text
invest portfolio import
invest portfolio reconcile
invest portfolio apply
invest portfolio record-activity
```

### Import

Input:

- copied/saved account HTML;
- institution/profile name if known.

Output:

- normalized account;
- positions;
- cash;
- lots if present;
- parsing warnings;
- confidence/status.

Import must not mutate the ledger.

### Reconcile

Compare an imported snapshot with current portfolio state.

Identify:

- new positions;
- removed positions;
- quantity changes;
- cash changes;
- lot changes;
- unidentified securities;
- discrepancies.

Do not infer transactions when multiple explanations are possible.

Example:

A position changing from 100 to 75 shares may indicate a sale, transfer, corporate action, or correction.

Report the state difference rather than inventing the transaction.

### Apply

Explicitly accept a reconciled snapshot as the new known account state.

Mutation must require an explicit `apply` command.

### Parser architecture

Keep parser extensibility simple.

Use:

```text
parsers/
    generic.py
    profiles.py
```

Broker-specific behavior is represented as declarative column/table aliases where practical.

Do not create a plugin framework.

The generic parser must support common tables containing columns equivalent to:

```text
symbol
description
quantity
price
market value
cost basis
gain/loss
acquisition date
```

Unsupported or ambiguous data must produce warnings rather than guesses.

---

# 6.2 Portfolio Summary

Command:

```text
invest portfolio summary
```

Return household and account-level:

- total portfolio value;
- cash;
- value by account;
- value by tax status;
- asset-class allocation;
- largest positions;
- unrealized gains/losses where basis exists;
- missing-data warnings;
- snapshot dates.

This command must never retrieve public web research.

It reports canonical local state only.

---

# 6.3 Tax Analysis

Commands:

```text
invest tax lots
invest tax analyze
invest tax harvest-candidates
```

This component is deterministic.

The LLM must never perform these calculations itself when the tools can answer them.

### Lot analysis

For each taxable lot calculate:

- acquisition date;
- remaining quantity;
- cost basis;
- current value;
- unrealized gain/loss;
- short-term or long-term status.

### Proposed sale analysis

Given:

```text
account
security
quantity or lots
assumed sale price
sale date
```

return:

- selected lots;
- realized gain/loss;
- ST gain/loss;
- LT gain/loss;
- household wash-sale warnings;
- affected accounts;
- estimated tax effect if configured;
- missing-information warnings.

### Lot-selection recommendation

For taxable accounts, support:

```text
SPECIFIC
FIFO
LIFO
HIFO
MIN_TAX
```

`MIN_TAX` chooses the available lots producing the lowest estimated current tax liability given configured tax rates.

Do not automatically mutate tax basis based on inferred wash sales.

Broker-provided basis remains authoritative.

### Wash-sale analysis

Evaluate known purchases across all loaded household accounts in the statutory ±30-day window around the proposed loss sale.

Include acquisitions in:

- taxable accounts;
- Traditional IRAs;
- Roth IRAs;
- other loaded investment accounts.

Output:

```text
NO_KNOWN_CONFLICT
POTENTIAL_CONFLICT
INSUFFICIENT_DATA
```

Never state that two securities are legally "substantially identical."

Replacement similarity is a separate analytical result.

### Tax configuration

Optional values:

```text
ordinary_income_rate
long_term_capital_gains_rate
niit_rate
state_capital_gains_rate
```

If rates are absent, return realized gains/losses without fabricated dollar tax savings.

---

# 6.4 Fund Holdings

Commands:

```text
invest fund holdings TICKER
invest fund compare FUND_A FUND_B
```

Use FMP structured holdings data.

Cache responses locally with source/as-of metadata.

### Fund holdings

Return the complete available holdings dataset, not merely top holdings.

Each constituent should include where available:

```text
security identifier
ticker
name
weight
shares
market value
```

Weights must be normalized consistently.

The output must state if the provider appears to supply only partial holdings.

### Fund comparison

Calculate:

```text
weighted holdings overlap
active share
number of shared holdings
percentage of assets represented by shared holdings
top shared holdings
largest unique exposures
sector differences if available
historical return correlation
expense ratios
```

Definitions:

```text
overlap = Σ min(weight_A_i, weight_B_i)

active_share = 0.5 × Σ abs(weight_A_i - weight_B_i)
```

Identifier normalization must occur before comparison.

This tool describes similarity.

It must not decide wash-sale legality.

---

# 6.5 Portfolio Look-Through Exposure

Command:

```text
invest portfolio exposure
```

Combine:

- direct securities;
- ETF holdings;
- mutual-fund holdings;
- cash;
- unsupported/unresolved assets.

Calculate household exposure to underlying securities.

Example:

If the user owns NVIDIA directly and indirectly through VTI and QQQ, report the aggregate NVIDIA exposure.

Return:

- direct value;
- indirect value;
- total value;
- percentage of household portfolio;
- contributing funds/accounts.

Also produce supported aggregations where reliable source data exists:

```text
sector
asset type
individual company
```

Do not fabricate geographic/style/factor classifications if source data is missing.

Unresolved exposure must appear explicitly as:

```text
unknown_exposure_value
unknown_exposure_percentage
```

---

# 6.6 Historical Data and Portfolio Analytics

Commands:

```text
invest market history
invest portfolio risk
```

Use FMP historical adjusted price data.

Required calculations:

### Security/fund

- total return;
- annualized return;
- annualized volatility;
- maximum drawdown;
- rolling return series;
- correlation.

### Portfolio

- historical volatility;
- maximum drawdown;
- position concentration;
- pairwise correlations for major positions;
- simple diversification metrics.

Do not add advanced optimization models in MVP.

Do not implement Black-Litterman, CVaR, factor models, or machine-learning forecasts.

Those are post-MVP unless a concrete use case proves necessary.

---

# 6.7 Portfolio Scenario Simulator

Command:

```text
invest portfolio simulate
```

Input is one or more hypothetical actions:

```text
BUY
SELL
MOVE_CASH
```

Simulation never modifies the database.

Calculate before/after:

- account values;
- cash;
- household allocation;
- look-through concentration;
- realized taxable gain/loss;
- ST/LT gain breakdown;
- wash-sale warnings;
- largest exposure changes;
- selected tax lots;
- estimated tax effect when configured.

Example:

```text
Sell $20,000 VTI from taxable account.
Buy $20,000 ITOT.
```

The agent should be able to compare several simulations without changing real state.

---

# 6.8 Security and Fund Screening

Commands:

```text
invest security screen
invest fund search
```

These tools provide structured candidate discovery where Chrome is inefficient.

They do not generate investment recommendations.

### Equity screen

Support filters available through FMP such as:

```text
market capitalization
sector
industry
country
price
dividend yield
valuation fields
profitability fields
growth fields
```

Only expose filters reliably supported by the configured provider.

### Fund search

Support available structured criteria such as:

```text
ETF vs mutual fund
fund category/style when available
expense ratio
AUM
issuer
```

The browser-equipped agent is responsible for qualitative follow-up research on candidates.

---

# 6.9 Tax-Loss-Harvesting Replacement Search

Command:

```text
invest fund replacements ORIGINAL_FUND
```

This command combines existing structured capabilities.

Candidate ranking may use:

- holdings overlap;
- active share;
- historical return correlation;
- expense-ratio difference;
- fund type;
- benchmark metadata when available.

Return raw metrics plus a ranking score.

The score is a portfolio-similarity score only.

Output must contain:

```text
"This score does not determine whether securities are substantially identical for tax purposes."
```

Do not implement a legal determination algorithm.

---

# 6.10 Bond Analysis

Command:

```text
invest bond analyze
```

MVP supports analysis of a known bond.

Input may include:

```text
identifier
face value
coupon
maturity
frequency
clean price
call schedule if known
```

Use QuantLib for deterministic calculations.

Return where calculable:

- accrued interest;
- dirty price;
- yield to maturity;
- yield to worst when call information is available;
- modified duration;
- convexity.

Do not implement a comprehensive bond-market screener or paid bond-data integration in MVP.

The browser agent may research candidate bonds publicly and pass known terms into this tool.

---

# 6.11 Manual Activity Recording

Command:

```text
invest portfolio record-activity
```

This supports the human-execution workflow.

Example:

```text
BUY 25 ITOT @ 142.17
account=taxable
date=2026-10-08
fee=0
```

The command validates that:

- account exists;
- security resolves;
- quantity and values are valid;
- resulting cash/position state is internally consistent where enough data exists.

The tool must show the proposed state change before committing unless `--yes` is supplied.

Subsequent account snapshots may supersede position state but must not silently delete activity history.

---

# 7. Explicitly Out of Scope

Do not implement in MVP:

- order placement;
- brokerage authentication;
- brokerage APIs;
- Plaid;
- MCP servers;
- automated trade execution;
- autonomous portfolio changes;
- dedicated news APIs;
- social-media sentiment;
- LLM calls;
- vector/RAG infrastructure;
- SEC document ingestion;
- earnings-call transcription;
- options analytics;
- crypto;
- tax-form preparation;
- authoritative tax filing calculations;
- full wash-sale basis adjustment accounting;
- comprehensive municipal/corporate bond discovery;
- portfolio optimization algorithms beyond scenario analysis;
- mobile/web GUI;
- cloud synchronization;
- multi-user accounts.

---

# 8. Agent Usage Contract

Document the intended division of responsibilities.

The agent should use Chrome for:

```text
recent news
qualitative company research
investment theses
industry developments
SEC filings
management commentary
macroeconomic developments
candidate discovery
fact verification
```

The agent should use CLI tools whenever a question depends on:

```text
the user's portfolio
account balances
tax lots
cost basis
wash-sale analysis
exact fund holdings
large holdings comparisons
look-through exposure
historical time series
repeatable calculations
structured screens
hypothetical portfolio changes
persistent state
```

The README must include this policy because it is a core part of the architecture.

---

# 9. External Data Failure Rules

External data may be unavailable, delayed, partial, or inconsistent.

Commands must fail conservatively.

Never replace missing data with model assumptions.

Examples:

If fund holdings are unavailable:

```text
status = DATA_UNAVAILABLE
```

not an estimate from top holdings.

If lot basis is unavailable:

```text
tax_analysis = INSUFFICIENT_DATA
```

not a guessed FIFO basis.

If historical prices contain gaps:

return warnings and the exact usable period.

The agent can then use Chrome or ask the human for more information.

---

# 10. Caching

Use SQLite for cache metadata and local compressed JSON files only if payload size makes SQLite storage impractical.

Default TTLs:

```text
quotes/current market metadata: 15 minutes
historical daily prices: 24 hours
fund holdings: 24 hours
fund metadata: 24 hours
security metadata: 7 days
```

If the source provides an explicit holdings `as_of` date, expose it even when the response was retrieved recently.

Support:

```text
--refresh
```

to bypass cache.

No background refresh jobs.

---

# 11. BDD Development Requirement

All work follows strict red-green BDD.

For every implementation chunk:

1. write all required BDD feature scenarios first;
2. run them;
3. confirm they fail for the expected missing behavior;
4. investigate any scenario that unexpectedly passes;
5. only then write production code;
6. run the feature suite until green;
7. run the complete repository test suite;
8. update documentation before considering the chunk complete.

Use `pytest-bdd`.

Scenarios must describe observable domain behavior, not internal calls.

Good:

```gherkin
Scenario: A taxable loss sale conflicts with a recent IRA purchase
  Given the taxable account owns 100 shares of VTI at a loss
  And the Roth IRA purchased VTI 10 days ago
  When the user analyzes selling the taxable VTI shares today
  Then the result identifies a potential wash-sale conflict
  And the Roth IRA purchase is identified as the conflicting acquisition
```

Bad:

```gherkin
When TaxService calls LotRepository
Then WashSaleChecker should be invoked
```

External APIs may be replaced by deterministic fixture responses during tests.

Internal modules should not be heavily mocked.

Tests must remain valid after reasonable internal refactoring.

---

# 12. Implementation Chunks

The following chunks are intentionally separated to minimize overlapping work.

A chunk does not begin until its dependencies are complete.

---

## Chunk 1 — Foundation, Ledger, Import, and Reconciliation

**Dependencies: none.**

Build:

- project/package skeleton;
- CLI;
- config loading;
- SQLite schema/migrations;
- canonical account/security/position/lot/activity models;
- HTML importer;
- snapshot reconciliation;
- snapshot application;
- manual activity recording;
- portfolio summary.

BDD scenarios should cover:

- first account import;
- repeated identical import;
- changed position;
- changed cash balance;
- unknown security;
- account containing lot data;
- account without lot data;
- ambiguous state changes;
- explicit apply behavior;
- manual activity recording;
- no raw HTML persistence.

Deliverable:

The agent can reliably establish and maintain current household portfolio state from copied HTML.

---

## Chunk 2 — Tax-Lot and Wash-Sale Analysis

**Dependencies: Chunk 1.**

Build only tax/accounting analysis:

- lot classification;
- unrealized gains/losses;
- sale simulation;
- ST/LT separation;
- FIFO/LIFO/HIFO/specific-lot selection;
- minimum-current-tax lot selection;
- household wash-sale-window detection;
- optional tax-rate estimates;
- harvesting-candidate identification.

Do not work on fund holdings or portfolio exposure in this chunk.

BDD scenarios should include:

- short-term gain;
- long-term gain;
- mixed-lot sale;
- harvesting a loss;
- taxable-account conflicting purchase;
- IRA conflicting purchase;
- no conflicting purchase;
- missing transaction history;
- missing lot detail;
- tax rates absent;
- configured tax rates.

Deliverable:

The agent can ask precise tax-impact questions using deterministic results.

---

## Chunk 3 — Structured Market Data and Fund Comparison

**Dependencies: Chunk 1.**

Build:

- FMP client;
- cache;
- security normalization;
- historical prices;
- ETF/mutual-fund metadata;
- complete available holdings retrieval;
- fund-to-fund holdings comparison.

Do not implement portfolio look-through yet.

BDD scenarios use recorded/static provider fixtures.

Cover:

- successful holdings retrieval;
- partial holdings warning;
- identifier normalization;
- stale-cache refresh;
- API failure;
- holdings overlap;
- active share;
- historical correlation.

Deliverable:

The agent can compare two funds quantitatively and exhaustively rather than relying on browser-visible top holdings.

---

## Chunk 4 — Household Look-Through Exposure

**Dependencies: Chunks 1 and 3.**

Build only portfolio exposure aggregation.

Combine direct positions with ETF and mutual-fund constituents.

Support:

- company/security exposure;
- direct vs indirect exposure;
- contributing positions/accounts;
- sector aggregation where structured data exists;
- unknown/unresolved exposure.

BDD scenarios should include:

- security held directly and through one ETF;
- security held through multiple funds;
- nested user positions across accounts;
- missing fund holdings;
- weights not summing to exactly 100%;
- cash;
- unresolved assets.

Deliverable:

The agent can answer "What do I actually own?" across the entire household portfolio.

---

## Chunk 5 — Scenario Simulation and Portfolio Risk

**Dependencies: Chunks 1–4.**

Build:

- hypothetical buys/sells;
- no-write simulations;
- before/after allocation;
- tax effects via Chunk 2;
- exposure changes via Chunk 4;
- historical volatility;
- maximum drawdown;
- concentration;
- correlation metrics.

Do not add advanced optimizer libraries.

BDD scenarios should cover:

- taxable sale and replacement purchase;
- retirement-account rebalance;
- insufficient cash;
- attempted sale exceeding position;
- change in indirect concentration;
- simulated transaction leaves ledger unchanged.

Deliverable:

The agent can safely test portfolio decisions before asking the human to trade.

---

## Chunk 6 — Structured Discovery and TLH Replacement Search

**Dependencies: Chunks 2, 3, and 5.**

Build:

- equity screening;
- fund search;
- fund replacement ranking;
- structured candidate metrics.

Use browser research for qualitative conclusions.

Do not build a recommendation model.

BDD scenarios should cover:

- filtering candidates;
- unavailable filter;
- ranking similar funds;
- exclusion of original fund;
- candidate with high correlation but low holdings overlap;
- mandatory substantially-identical disclaimer.

Deliverable:

The agent can efficiently identify candidates before performing browser research.

---

## Chunk 7 — Fixed-Income Analysis

**Dependencies: Chunk 1.**

This chunk may proceed after Chunk 1 but should be implemented after core equity/fund functionality unless fixed-income work becomes immediately necessary.

Build:

- bond security representation;
- deterministic QuantLib calculations;
- Treasury/fixed-income calculations for known securities;
- graceful handling of missing call schedules or prices.

Do not build a commercial bond-feed integration.

BDD scenarios should cover:

- fixed-rate bond YTM;
- accrued interest;
- duration;
- callable bond with supplied call schedule;
- insufficient bond terms.

Deliverable:

The agent can reason correctly about bonds it discovers through the browser or encounters in the portfolio.

---

## Chunk 8 — Hardening, Agent Documentation, and MVP Acceptance

**Dependencies: Chunks 1–7.**

No substantial new functionality.

Complete:

- CLI consistency;
- JSON schemas;
- error handling;
- provenance metadata;
- cache behavior;
- privacy review;
- README;
- agent usage guide;
- sample configuration;
- example HTML-import workflow;
- example tax-loss-harvesting workflow;
- example fund-comparison workflow;
- example portfolio-simulation workflow.

Run the entire BDD suite against representative anonymized portfolio fixtures.

Deliverable:

A new developer or agent operator can install and use the complete MVP without undocumented assumptions.

---

# 13. Test Fixtures

Repository tests must include anonymized deterministic fixtures representing:

```text
taxable brokerage account
Traditional IRA
Roth IRA
cash/bank account
stock holdings
ETF holdings
mutual-fund holdings
individual bond
multiple tax lots
recent purchases
loss positions
cash balances
```

Use obviously synthetic account identifiers and financial values.

External API fixtures must be checked into the test suite where licensing permits, reduced to the minimum fields needed for test behavior.

Tests must not require:

- internet access;
- real API keys;
- actual financial accounts.

---

# 14. Documentation Requirements

Maintain:

```text
README.md
docs/agent-usage.md
docs/data-model.md
docs/tax-limitations.md
docs/data-sources.md
```

README must contain:

- installation;
- initial configuration;
- first account import;
- common CLI examples;
- testing instructions.

`agent-usage.md` must explain Chrome-vs-CLI responsibilities.

`tax-limitations.md` must clearly state:

- this software is analytical tooling, not tax preparation;
- imported broker basis remains authoritative;
- wash-sale detection is based only on loaded household information;
- substantially-identical determinations are not automated;
- unknown outside accounts or spouse activity may affect real tax treatment.

---

# 15. Privacy and Security Requirements

The application is local-first.

Requirements:

- no telemetry;
- no cloud database;
- no account credentials;
- no brokerage passwords;
- no browser cookies;
- raw imported HTML is not persisted;
- API keys are loaded from environment variables or local config;
- configuration containing secrets must be excluded from version control;
- logs must not contain full account identifiers or raw imported pages.

Display account identifiers in redacted form where possible.

---

# 16. Performance Targets

This is not a high-frequency system.

Targets on ordinary desktop hardware:

```text
portfolio summary: <1 second
tax-lot analysis: <1 second
portfolio scenario calculation: <2 seconds excluding remote data retrieval
cached fund comparison: <2 seconds
HTML import/reconciliation: <5 seconds for normal account pages
```

Remote API latency is excluded.

Do not introduce concurrency unless profiling demonstrates a real problem.

---

# 17. MVP Acceptance Criteria

The MVP is complete when the following conversation can be supported reliably:

> "I'm concerned that my portfolio is too concentrated in mega-cap technology. Show me my real exposure including ETFs and mutual funds. I don't want to realize more than $5,000 of long-term gains. Look for positions that could be tax-loss harvested, identify possible replacement funds, and show me what the portfolio would look like after several alternatives."

The agent must be able to obtain deterministic answers by composing CLI tools for:

```text
portfolio state
fund holdings
look-through exposure
tax lots
wash-sale risk
fund comparisons
historical correlations
candidate replacements
scenario simulation
```

The agent may then use Chrome to investigate:

```text
recent news
current investment theses
company/fund developments
macroeconomic conditions
qualitative risks
```

A second required workflow is:

> "I manually executed the trades we discussed. Here is the current account page."

The system must:

1. parse the supplied HTML;
2. compare it with previous state;
3. show detected changes;
4. allow explicit acceptance;
5. update the canonical ledger;
6. leave an auditable snapshot record.

A third required workflow is:

> "I'm considering this bond. Here are its terms and current price."

The system must calculate the relevant fixed-income metrics without requiring an LLM to perform financial math.

---

# 18. Definition of Done

Each implementation chunk is complete only when:

- all planned BDD scenarios were written before production implementation;
- the scenarios were observed failing for the expected reason;
- implementation makes them green;
- the entire repository test suite passes;
- no behavior depends on internet access during tests;
- CLI output is valid documented JSON;
- error behavior is covered;
- relevant documentation is updated;
- no new architecture or dependency has been introduced outside this PRD without an explicit requirement change.

The MVP is complete only when all chunks are green and the three acceptance workflows above work against representative local fixtures.

---

# 19. Post-MVP Candidates

Do not implement these during MVP.

Possible future additions:

- better institutional fund data such as Morningstar;
- premium financial-news feeds;
- realtime market data beyond FMP;
- structured SEC/XBRL ingestion;
- commercial corporate/municipal bond data;
- advanced risk optimization;
- asset-location optimization;
- automatic household rebalance generation;
- options analytics;
- broker read-only APIs;
- UI/dashboard;
- automated trade proposal tracking;
- account-specific importer profiles for additional institutions.

Post-MVP work should be driven by observed failures of the agent/browser + deterministic-tool architecture, not anticipated complexity.

---

# 20. Architectural North Star

The system should remain intentionally asymmetric:

```text
                    FRONTIER AGENT
                  /                \
                 /                  \
       Chrome / public web        Local CLI
       -------------------        ---------
       News                       Portfolio state
       Research                   Tax lots
       SEC filings                Fund holdings
       Ideas                      Exposure
       Qualitative analysis       Historical math
       Current developments       Simulations
       Candidate discovery        Structured screens
                                  Bond calculations
                    \                /
                     \              /
                      HUMAN DECISION
                            ↓
                    MANUAL TRADE ONLY
```

The local software does not attempt to replace the agent.

The agent does not attempt to replace deterministic financial software.

The human does not delegate trade execution.

That separation is the defining product constraint of the MVP.