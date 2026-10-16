def migrate(cr, version):
    cr.execute(
        """
        UPDATE community_meeting_agenda_item AS item
           SET agenda_type_id = data.res_id
          FROM ir_model_data AS data
         WHERE data.module = 'community_meetings'
           AND data.model = 'community.meeting.agenda.type'
           AND data.name = CASE item.kind
               WHEN 'information' THEN 'agenda_type_information'
               WHEN 'decision' THEN 'agenda_type_decision'
               ELSE 'agenda_type_discussion'
           END
           AND item.agenda_type_id IS NULL
        """
    )
    cr.execute("ALTER TABLE community_meeting_agenda_item ALTER COLUMN agenda_type_id SET NOT NULL")
