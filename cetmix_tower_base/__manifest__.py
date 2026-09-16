# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Base",
    "summary": "Core access groups, menus and mixins for Cetmix Tower",
    "version": "18.0.0.0.0",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "pre_init_hook": "pre_init_hook",
    "depends": [
        "base_setup",
    ],
    "data": [
        "security/cetmix_tower_base_groups.xml",
        "security/ir.model.access.csv",
        "security/cx_tower_tag_security.xml",
        "views/cx_tower_tag_views.xml",
        "views/res_config_settings_views.xml",
        "views/menuitems.xml",
    ],
}
