def migrate(cr, version):
    cr.execute(
        """
        UPDATE community_meeting_agenda_item
           SET decision_result = 'pending'
         WHERE kind = 'decision'
           AND decision_result IS NULL
        """
    )
