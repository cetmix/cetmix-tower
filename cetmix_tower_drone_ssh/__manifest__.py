# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Drone SSH",
    "summary": "Run Cetmix Tower SSH commands on external drones",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "auto_install": False,
    "depends": ["cetmix_tower_drone", "cetmix_tower_server"],
    "data": [
        "views/cx_tower_command_log_views.xml",
        "views/cx_tower_drone_controller_views.xml",
        "views/cx_tower_drone_job_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [
        "demo/cx_tower_drone_controller_demo.xml",
    ],
}
