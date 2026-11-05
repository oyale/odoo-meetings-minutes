{
    "name": "Community Meetings - Calendar Integration",
    "summary": "Create private Calendar invitations for scheduled community meetings",
    "version": "18.0.1.0.8",
    "category": "Productivity/Calendar",
    "license": "AGPL-3",
    "author": "Pelayo García",
    "website": "https://github.com/oyale/odoo-meetings-minutes/tree/18.0/community_meetings_calendar",
    "maintainers": ["oyale"],
    "development_status": "Beta",
    "depends": ["community_meetings", "calendar"],
    "data": ["views/calendar_event_views.xml", "views/meeting_views.xml"],
    "assets": {
        "web.assets_backend": [
            "community_meetings_calendar/static/src/calendar_popover.js",
            "community_meetings_calendar/static/src/navigation_action.js",
            "community_meetings_calendar/static/src/navigation_action.xml",
        ],
    },
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
