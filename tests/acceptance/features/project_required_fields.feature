Feature: Require a project when creating a task from a meeting follow-up

  @project @cm_project_002
  Scenario: Create and Link requires an alternate project
    Given a project-required follow-up has a configured project
    When I choose another project but leave it empty
    Then the project-required error appears and no task is linked
