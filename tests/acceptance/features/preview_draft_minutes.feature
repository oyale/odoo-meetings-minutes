Feature: Preview draft minutes before approval
  As a meeting editor
  I want to preview the saved draft minutes
  So that I can review their final layout before approval

  Background:
    Given I can read the meeting

  @core @cm_preview_001
  Scenario: Review the draft without changing it
    Given the meeting is Held or has draft minutes
    When I choose Preview Minutes
    Then the saved minutes open in a read-only preview
    And I can choose Return to meeting to edit
    And the meeting and saved draft remain unchanged
    When I choose Return to meeting to edit
    Then I return to the meeting editor
