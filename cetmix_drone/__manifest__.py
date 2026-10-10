# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Drone",
    "summary": "Run long work on external workers and get the result back in Odoo",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://drone.cetmix.com",
    "live_test_url": "https://drone.cetmix.com",
    "images": ["static/description/banner.png"],
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["cetmix_tower_base"],
    "data": [
        "security/cetmix_drone_groups.xml",
        "security/ir.model.access.csv",
        "security/cx_drone_security.xml",
        "data/ir_cron.xml",
        "views/cx_drone_controller_views.xml",
        "views/cx_drone_skill_views.xml",
        "views/cx_drone_job_views.xml",
        "views/res_config_settings_views.xml",
        "views/menuitems.xml",
        "wizards/cx_drone_payload_key_wizard_views.xml",
    ],
    "demo": [
        "demo/res_users_demo.xml",
    ],
}
