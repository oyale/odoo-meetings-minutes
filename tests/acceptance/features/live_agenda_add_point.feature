Feature: Add agenda points during a live meeting
  As a meeting editor
  I want to add a point from the live agenda
  So that new topics can join the current discussion

  @core @cm_agenda_001
  Scenario: Add a discussion point to a running meeting
    Given a running meeting accepts new agenda points
    When I add a discussion point from the live agenda
    Then the new point appears in the live agenda and is saved on the meeting
