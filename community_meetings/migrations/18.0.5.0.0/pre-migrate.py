REPLACED_VIEW = "view_series_preparation"


def migrate(cr, version):
    # This inherited view still references followup_policy/default_followup_kind,
    # fields removed in this version. Odoo validates a base view against every
    # inherited view already in the registry; the series base form loads before
    # this inheritor, so its stale arch would abort the update. Drop it (the data
    # file recreates it with the new fields later in this same run). Base views
    # in the same file are simply rewritten, so they need no special handling.
    cr.execute(
        """
        DELETE FROM ir_ui_view
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'community_meetings' AND model = 'ir.ui.view'
                AND name = %s
         )
        """,
        (REPLACED_VIEW,),
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'community_meetings' AND model = 'ir.ui.view'
           AND name = %s
        """,
        (REPLACED_VIEW,),
    )
