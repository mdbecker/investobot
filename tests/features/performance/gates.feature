Feature: Fixed performance result gates
  Synthetic result JSON tests gate arithmetic without making machine timing claims.

  Scenario Outline: Strict paired measurement and certification contracts
    Given fixed synthetic benchmark-result JSON
    When the public gate evaluates "<rule>"
    Then the outcome is "<outcome>"

    Examples:
      | rule                       | outcome                 |
      | inventory_missing          | FAIL                    |
      | inventory_unrunnable       | FAIL                    |
      | inventory_unclassified     | FAIL                    |
      | inventory_missing_extended | FAIL                    |
      | inventory_complete         | PASS                    |
      | median_fail                | FAIL                    |
      | median_tie                 | PASS                    |
      | median_unrounded           | FAIL                    |
      | missing_case               | FAIL                    |
      | timeout                    | FAIL                    |
      | oom                        | FAIL                    |
      | invalid_output             | FAIL                    |
      | exit_error                 | FAIL                    |
      | cumulative_fail            | FAIL                    |
      | baseline_rewritten         | FAIL                    |
      | reference_changed          | FAIL                    |
      | unapproved_rebaseline      | FAIL                    |
      | self_asserted_rebaseline   | FAIL                    |
      | null_resource              | FAIL                    |
      | negative_timing            | FAIL                    |
      | batch_repetitions_mismatch | FAIL                    |
      | resource_peak_rss_bytes    | FAIL                    |
      | resource_persisted_bytes   | FAIL                    |
      | resource_temp_bytes        | FAIL                    |
      | p95_fail                   | FAIL                    |
      | p95_tie                    | PASS                    |
      | scaling_fail               | FAIL                    |
      | scaling_tie                | PASS                    |
      | scaling_wrong_counts       | FAIL                    |
      | diagnostics                | FAIL                    |
      | retry_pass                 | NOISY_FIRST_MEASUREMENT |
      | retry_fail                 | FAIL                    |
      | retry_error                | FAIL                    |
      | fixture_changed            | FAIL                    |
      | dimensions_changed         | FAIL                    |
      | recipe_changed             | FAIL                    |
      | runner_changed             | FAIL                    |
      | omitted_records            | FAIL                    |
      | wrong_output               | FAIL                    |
      | budget_fail                | FAIL                    |
      | budget_tie                 | PASS                    |
      | budget_wrong_runner        | FAIL                    |
      | short_batch                | FAIL                    |
      | insufficient_samples       | FAIL                    |
      | aggregate_pr               | STATISTICS              |
      | aggregate_retrieval        | STATISTICS              |
      | aggregate_bulk             | STATISTICS              |
