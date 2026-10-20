Feature: Control previous discussion during point carryover
  As a meeting editor
  I want to hide earlier discussion when a point continues
  So that later meetings show only context I still want to carry forward

  @core @cm_carryover_003
  Scenario: Hiding and restoring earlier discussion affects later continuations
    Given an accepted point has earlier debate notes and a destination meeting
    Then its earlier notes are read-only context
    When I start the current meeting and point
    And I hide the previous discussion
    Then the source notes are preserved and hidden on the current point
    When I accept the point in the later meeting
    Then its previous discussion does not include the hidden source notes
    When I restore the previous discussion on the current point
    Then the later continuation shows the restored source notes
