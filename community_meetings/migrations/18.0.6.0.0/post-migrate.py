def migrate(cr, version):
    cr.execute("SELECT to_regclass('tmp_topic_presenter')")
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE community_meeting_topic t
           SET presenter_partner_id = tmp.partner_id
          FROM tmp_topic_presenter tmp
         WHERE tmp.topic_id = t.id
           AND t.presenter_partner_id IS NULL
        """
    )
    cr.execute("DROP TABLE IF EXISTS tmp_topic_presenter")
