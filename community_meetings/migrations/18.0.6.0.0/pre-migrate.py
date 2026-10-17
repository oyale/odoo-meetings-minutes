def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'community_meeting_agenda_item'
           AND column_name = 'presenter_partner_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TEMP TABLE tmp_topic_presenter AS
        SELECT DISTINCT ON (topic_id) topic_id, presenter_partner_id AS partner_id
          FROM community_meeting_agenda_item
         WHERE presenter_partner_id IS NOT NULL
         ORDER BY topic_id, id DESC
        """
    )
