def uninstall_hook(env):
    env["calendar.event"].sudo()._community_meetings_calendar_uninstall_cleanup()
