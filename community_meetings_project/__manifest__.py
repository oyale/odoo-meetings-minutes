{
    "name": "Community Meetings - Project Tasks",
    "summary": "Link existing Odoo Project tasks to meetings",
    "version": "18.0.3.1.6",
    "category": "Services/Project",
    "license": "AGPL-3",
    "author": "Pelayo García",
    "website": "https://github.com/oyale/odoo-meetings-minutes/tree/18.0/community_meetings_project",
    "maintainers": ["oyale"],
    "development_status": "Beta",
    "depends": ["community_meetings", "project"],
    "data": [
        "security/ir.model.access.csv",
        "data/followup_kinds.xml",
        "views/project_views.xml",
    ],
    "post_init_hook": "post_init_allow_project_kinds",
    "assets": {
        "web.assets_backend": [
            "community_meetings_project/static/src/live_meeting/live_meeting.js",
            "community_meetings_project/static/src/live_meeting/live_meeting.xml",
        ],
    },
    "installable": True,
    "application": False,
}
