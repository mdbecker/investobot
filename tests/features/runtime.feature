Feature: Container-only runtime dependencies
  Scenario: Dependencies remain outside the shared project directory
    Given the Docker application environment
    When I inspect its dependency location
    Then the virtual environment is stored under opt
    And the invest entry point is available
