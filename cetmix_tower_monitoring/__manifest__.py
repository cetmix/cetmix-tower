# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Monitoring",
    "summary": "Current server and jet metrics in Cetmix Tower",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["cetmix_tower_webhook", "cx_web_refresh_from_backend"],
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_metric_security.xml",
        "data/ir_cron.xml",
        "views/cx_tower_metric_views.xml",
        "views/cx_tower_metric_value_views.xml",
        "views/cx_tower_server_views.xml",
        "views/cx_tower_jet_views.xml",
        "views/res_config_settings_views.xml",
        "views/menuitems.xml",
    ],
    "demo": [
        "demo/cx_tower_command_demo.xml",
        "demo/cx_tower_plan_demo.xml",
        "demo/cx_tower_metric_demo.xml",
        "demo/cx_tower_jet_template_metric_demo.xml",
        "demo/cx_tower_webhook_demo.xml",
    ],
}
