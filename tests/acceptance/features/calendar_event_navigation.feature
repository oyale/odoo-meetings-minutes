Feature: Navigate between a meeting and its Calendar event
  As a meeting editor
  I want to open the linked Calendar event and return to the meeting
  So that both records stay connected and easy to reach

  @calendar @cm_calendar_001
  Scenario: Open the linked records from either form
    Given a scheduled meeting has a linked Calendar event
    When I open the Calendar event from the meeting form
    Then the Calendar event is linked to this meeting
    When I open the meeting from the Calendar event
    Then the same meeting form is open
    When I reopen its Calendar event from the meeting form
    Then the same Calendar event form is open
