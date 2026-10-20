Feature: Accept a requested agenda point in its destination meeting
  As a meeting editor
  I want to request that an unfinished point continue elsewhere
  So that the destination meeting can include it with its origin preserved

  @core @cm_carryover_001
  Scenario: A meeting editor accepts the point in its destination
    Given an unfinished agenda point and an eligible destination meeting exist
    When I request to move the point to that meeting
    Then I accept it there and the linked point appears in that meeting

  @core @cm_carryover_004
  Scenario: An editor dismisses a requested carryover
    Given an unfinished agenda point and an eligible destination meeting exist
    When I request to move the point to that meeting
    Then I dismiss the carryover from the destination meeting
