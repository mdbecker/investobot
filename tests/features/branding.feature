Feature: Investobot product identity
  Scenario: The inspection page uses the Investobot name
    When I inspect the packaged local page
    Then its title and brand name are Investobot
  Scenario: Default configuration and ledger paths use Investobot
    Given no explicit path overrides
    When I inspect the default ledger and load the default configuration
    Then the ledger and configuration use Investobot directories
  Scenario: The installed distribution uses the Investobot name
    When I inspect installed package metadata
    Then the Investobot distribution is installed
