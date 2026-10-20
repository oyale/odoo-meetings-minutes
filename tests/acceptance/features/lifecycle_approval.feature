Feature: Approve minutes only when the agenda is complete
  As a meeting approver
  I want approval blocked when no agenda points exist
  So that an empty set of minutes cannot become an approved record

  @core @cm_lifecycle_003
  Scenario: Minutes without agenda points cannot be approved
    Given a draft of minutes has no agenda points
    When I choose Approve Minutes from its meeting form
    Then the form explains that an agenda point is required
    And the draft remains unapproved without a new revision
