Feature: Require a destination when requesting an agenda carryover
  As a meeting editor
  I want to choose a destination for an unfinished point
  So that the carryover can be routed

  @core @cm_carryover_002
  Scenario: Do not create a carryover without a destination
    Given an unfinished agenda point is in a meeting outside a series
    When I request to move the point without choosing a destination
    Then the destination error appears and no carryover is created
