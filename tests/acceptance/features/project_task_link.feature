Feature: Create and link a Project task from a meeting follow-up
  As a meeting editor with Project access
  I want to assign a follow-up to a Project task
  So that the task is available from both records

  @project @cm_project_001
  Scenario: Create a task in another project and link it
    Given a meeting has a Project-required follow-up and an alternate project
    When I create the follow-up task in the alternate project
    Then the task is linked to the meeting follow-up

  @project @cm_project_003
  Scenario: Link an existing Project task to a follow-up
    Given a Project-required follow-up and an existing task are available
    When I select the existing task in the follow-up wizard
    Then the existing task is linked to the meeting follow-up
