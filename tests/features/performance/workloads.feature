Feature: Complete separately measured offline critical workflows
  Scenario: Published inventory has complete executable coverage
    Given the complete fixed critical-workflow inventory
    When runnable inventory coverage is checked
    Then every named subcase is runnable with no unclassified expensive public path

  Scenario Outline: Real <case_id> operation preserves its behavioral workload
    Given the isolated real workload <case_id>
    When one explicitly reduced test-profile observation is measured offline
    Then the separately timed operation proves correct output and complete test-profile counts

    Examples:
      | case_id |
      | P01.cli-startup |
      | P01.tools-list |
      | P01.tools-describe |
      | P01.dashboard-overview |
      | P02.html-preview |
      | P02.reconcile |
      | P02.apply |
      | P02.idempotent-reimport |
      | P02.check |
      | P03.activity-append |
      | P03.corrected-snapshot |
      | P03.summary |
      | P03.planning-read |
      | P04.backup |
      | P04.verify |
      | P04.restore-staging |
      | P04.schema-migration |
      | P04.manifest-verify |
      | P05.household-performance |
      | P05.account-performance |
      | P05.linked-flow-metrics |
      | P05.incomplete-coverage |
      | P06.lots |
      | P06.specific-disposal |
      | P06.budget |
      | P06.harvest-candidates |
      | P06.harvest-plan |
      | P06.household-wash-review |
      | P07.target-diff |
      | P07.simulate |
      | P07.monthly-proposal |
      | P07.quarterly-proposal |
      | P08.persist-20-plans |
      | P08.list |
      | P08.compare-20 |
      | P08.show |
      | P08.markdown-export |
      | P09.holdings-hit |
      | P09.holdings-miss |
      | P09.compare-hit |
      | P09.compare-miss |
      | P09.search-hit |
      | P09.search-miss |
      | P09.replacements-hit |
      | P09.replacements-miss |
      | P09.screen-hit |
      | P09.screen-miss |
      | P09.history-read-hit |
      | P09.history-read-miss |
      | P09.history-metrics-hit |
      | P09.history-metrics-miss |
      | P10.recursive-exposure |
      | P10.top-issuers |
      | P10.research-universe |
      | P10.incomplete-coverage |
      | P11.data-snapshot |
      | P11.pinned-parquet-read |
      | P11.temporal-join |
      | P11.observation-aggregation |
      | P12.run-ten-years |
      | P12.compare-three |
      | P12.identical-repeat |
      | P12.unavailable-history |
      | P13.news-validate |
      | P13.news-import |
      | P13.political-validate |
      | P13.political-import |
      | P13.earnings-validate |
      | P13.earnings-import |
      | P13.competitive-validate |
      | P13.competitive-import |
      | P13.insiders-validate |
      | P13.insiders-import |
      | P13.fund-diligence-validate |
      | P13.fund-diligence-import |
      | P13.history-list |
      | P13.context |
      | P13.changes |
      | P13.compare |
      | P13.portfolio-report |
      | P14.text-top10 |
      | P14.semantic-top10 |
      | P14.hybrid-filtered-top10 |
      | P14.rebuild-after-deletion |
      | P14.incremental-ingest |
      | P15.monthly-report-sequence |
      | P15.top-issuer-research-sequence |
      | P03.linked-cash-transfer |
      | P05.hypothetical-risk |
      | P09.quote-hit |
      | P09.quote-miss |
      | P13.news-list |
      | P13.news-show |
      | P13.news-summary |
      | P13.political-list |
      | P13.political-show |
      | P13.political-summary |
      | P13.earnings-list |
      | P13.earnings-show |
      | P13.earnings-summary |
      | P13.competitive-list |
      | P13.competitive-show |
      | P13.competitive-summary |
      | P13.insiders-list |
      | P13.insiders-show |
      | P13.insiders-summary |
      | P13.fund-diligence-list |
      | P13.fund-diligence-show |
      | P13.fund-diligence-summary |
      | P13.competitive-matrix |
      | P13.insiders-activity |
      | P13.insiders-ownership |
      | P13.fund-diligence-holdings |
      | P13.research-plan |
