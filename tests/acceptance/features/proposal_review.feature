Feature: Submit and accept an agenda proposal
  @core @cm_proposal_001
  Scenario: An editor accepts a submitted point
    Given a meeting series allows a new point proposal
    When I submit a titled discussion point
    Then the proposal is visible for review and can be accepted
    And the point is admitted to the series agenda

  @core @cm_proposal_003
  Scenario: An editor rejects a submitted proposal
    Given a meeting series allows a new point proposal
    When I submit a proposal and reject it as an editor
    Then the proposal is rejected and is not admitted to the agenda
