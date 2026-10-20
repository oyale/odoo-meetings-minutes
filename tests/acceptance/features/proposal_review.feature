Feature: Submit and accept an agenda proposal
  @core @cm_proposal_001
  Scenario: An editor accepts a submitted point
    Given a meeting series allows a new point proposal
    When I submit a titled discussion point
    Then the proposal is visible for review and can be accepted
    And the point is admitted to the series agenda
