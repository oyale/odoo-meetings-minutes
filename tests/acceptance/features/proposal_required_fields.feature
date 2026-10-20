Feature: Reject incomplete agenda proposals

  @core @cm_proposal_002
  Scenario: Submit a proposal without a title
    Given an agenda proposal can be submitted for a series
    When I submit the proposal without a title
    Then the title validation is shown and no proposal is saved
