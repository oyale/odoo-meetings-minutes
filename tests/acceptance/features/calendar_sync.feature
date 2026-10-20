Feature: Keep the Calendar event synchronized with a meeting
  As a meeting editor
  I want event details to follow meeting changes
  So that attendees see the current schedule and location

  @calendar @cm_calendar_003
  Scenario: Meeting changes update its Calendar event
    Given a scheduled meeting has an eligible linked Calendar event
    When I change the meeting time, location and attendees in its form
    Then the linked Calendar event shows the updated details
