{
    "name": "Community Meetings - Calendar Integration",
    "summary": "Create private Calendar invitations for scheduled community meetings",
    "version": "18.0.1.0.0",
    "category": "Productivity/Calendar",
    "license": "AGPL-3",
    "depends": ["community_meetings", "calendar"],
    "data": ["views/calendar_event_views.xml", "views/meeting_views.xml"],
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
