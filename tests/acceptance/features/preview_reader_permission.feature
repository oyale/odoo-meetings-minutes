Feature: Keep draft minutes preview within editorial roles
  As a meeting reader
  I want draft minutes to remain unavailable to me
  So that preview access matches the editor and approver boundary

  @core @cm_preview_003
  Scenario: A reader cannot open draft minutes preview
    Given draft minutes exist and a reader account is configured
    When I attempt to preview them as that reader
    Then the reader sees no preview action or content and the endpoint denies access
