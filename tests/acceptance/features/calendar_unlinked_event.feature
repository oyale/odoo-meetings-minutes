Feature: Do not open a meeting from an unlinked Calendar event
  @calendar @cm_calendar_002
  Scenario: The Calendar event has no meeting association
    Given an unlinked Calendar event is open
    When I check whether the event offers Open Meeting
    Then the action is unavailable and the event remains unlinked
