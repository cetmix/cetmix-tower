# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Drone",
    "summary": "Run long work on external drones and get the result via callback",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["cetmix_tower_base"],
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_drone_security.xml",
        "data/ir_cron.xml",
        "views/cx_tower_drone_controller_views.xml",
        "views/cx_tower_drone_job_views.xml",
        "views/res_config_settings_views.xml",
        "views/menuitems.xml",
    ],
}
