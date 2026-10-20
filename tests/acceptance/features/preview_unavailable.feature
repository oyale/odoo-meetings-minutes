Feature: Preview minutes only after the meeting is held
  As a meeting editor
  I want preview access to follow the meeting lifecycle
  So that minutes cannot be previewed before they are ready

  @core @cm_preview_002
  Scenario: A scheduled meeting cannot be previewed
    Given a scheduled meeting that is not ready for minutes preview
    When I attempt to preview its minutes
    Then the preview action is unavailable in the meeting form
    And the server explains that the meeting must be held first
    And the meeting remains unchanged
