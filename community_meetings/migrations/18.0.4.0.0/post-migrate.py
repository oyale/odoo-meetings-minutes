"""Map the historical hardcoded meeting kind onto the seeded kind records."""


def migrate(cr, version):
    if not version:
        return
    for table in ("community_meeting", "community_meeting_series"):
        cr.execute(
            f"""
            UPDATE {table} AS target
               SET meeting_kind_id = kind.id
              FROM community_meeting_kind AS kind
             WHERE target.meeting_kind_id IS NULL
               AND target.meeting_kind = kind.code
            """
        )
        cr.execute(
            f"""
            UPDATE {table}
               SET meeting_kind_id = (
                       SELECT id FROM community_meeting_kind WHERE code = 'operational' LIMIT 1
                   )
             WHERE meeting_kind_id IS NULL
            """
        )
        cr.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS meeting_kind")
