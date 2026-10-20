Feature: Cancel a meeting from its form
  As a meeting editor
  I want to cancel a scheduled meeting
  So that its linked Calendar event is removed

  @calendar @cm_calendar_004
  Scenario: Cancelling the meeting removes its Calendar event
    Given a scheduled meeting has a linked Calendar event
    When I cancel the meeting from its form
    Then the meeting is cancelled and the Calendar event is removed
