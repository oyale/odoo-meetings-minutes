Feature: Let meeting readers preview draft minutes
  As a meeting reader
  I want to read draft minutes for a meeting I can access
  So that I can review them before they are approved

  @core @cm_preview_003
  Scenario: A reader with meeting access can preview draft minutes
    Given draft minutes exist and a reader account is configured
    When I attempt to preview them as that reader
    Then the reader can open the read-only preview and the endpoint returns its content
