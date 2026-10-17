from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # Legacy: old root menu xmlid removed from view definitions; drop it here.
    env = api.Environment(cr, SUPERUSER_ID, {})
    menu = env.ref("community_meetings.menu_community_meetings", raise_if_not_found=False)
    if menu:
        menu.unlink()
