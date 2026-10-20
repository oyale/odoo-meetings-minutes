Feature: Complete a meeting and approve its minutes
  As a meeting editor and a distinct approver
  I want to run a meeting through approval
  So that the approved minutes belong to the meeting that was held

  @core @cm_lifecycle_001
  Scenario: Create, hold and approve the same meeting
    Given I create and schedule a meeting with an agenda point in the UI
    When I hold the meeting in the live agenda
    And I sign in as the configured approver and approve the minutes
    Then the same meeting is approved and its minutes PDF opens
