def migrate(cr, version):
    # Old action_admit opened points without recording a proposal review.
    # Preserve their operational state and any known provenance: neither an
    # approver nor an approval date can be inferred retrospectively.
    cr.execute(
        """
        UPDATE community_meeting_topic
           SET proposal_status = 'legacy_admitted'
         WHERE proposal_status = 'submitted'
           AND state IN ('open', 'closed')
        """
    )
