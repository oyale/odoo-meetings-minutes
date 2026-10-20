Feature: Reject a stale live agenda point form
  As a meeting editor
  I want an open Add Point form to respect changes made by another session
  So that a point is not added after the meeting stops accepting additions

  @core @cm_agenda_002
  Scenario: Another session closes additions before the point is saved
    Given the Add Point form is open while a scheduled meeting accepts additions
    When another session finishes the meeting before I save the point
    Then the stale save is rejected and no new agenda point exists
