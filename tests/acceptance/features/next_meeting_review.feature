Feature: Review postponed agenda points at the next meeting
  As a meeting editor
  I want postponed points to be marked for review
  So that unresolved work is not forgotten

  @core @cm_next_review_001
  Scenario: Postpone a point and mark it for the next meeting
    Given a running meeting contains a discussion point that can be postponed
    When I postpone the point with a reason
    Then the point is postponed and marked for review at the next meeting

  @core @cm_next_review_002
  Scenario: Keep the review choice after reopening the meeting
    Given a running meeting contains a discussion point that can be postponed
    When I mark the point for review at the next meeting
    Then the choice remains checked after reopening the meeting
    When I clear the review choice
    Then the choice remains clear after reopening the meeting
