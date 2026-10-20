Feature: Schedule only meetings with a date and time
  As a meeting editor
  I want incomplete meetings to remain drafts
  So that scheduled meetings always have a date and time

  @core @cm_lifecycle_002
  Scenario: A meeting without a date cannot be scheduled
    Given a draft meeting without a date or time
    When I choose Schedule from its meeting form
    Then the form explains that a date and time are required
    And the meeting remains a draft without a scheduled date
