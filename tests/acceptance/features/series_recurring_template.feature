Feature: Add a recurring agenda point to a meeting series
  @core @cm_ser_003
  Scenario: Use a series template while preparing a meeting
    Given an editable meeting series is open
    When I add a recurring discussion point and prepare a meeting
    Then the recurring point is available for this meeting and remains active on the series

  @core @cm_ser_004
  Scenario: Skip a recurring point once and include it in a later meeting
    Given a recurring template is active on a meeting series
    When I omit it from one meeting and include it in a later meeting
    Then the skipped meeting has no occurrence and the later occurrence links to the first
