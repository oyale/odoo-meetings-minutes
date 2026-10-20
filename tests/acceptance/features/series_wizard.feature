Feature: Create a meeting series
  As a meeting editor
  I want to create a series with reusable defaults
  So that recurring meetings can be prepared consistently

  @core @cm_ser_001
  Scenario: Create a series
    Given the meeting series wizard is open
    When I complete the series details and choose Create Series
    Then the series appears in Meeting Series with its saved defaults

  @core @cm_ser_002
  Scenario: Leave the series name blank
    Given the meeting series wizard is open with no name
    When I try to continue without a series name
    Then the required-name validation remains active and no series is persisted
