# Copyright Cetmix OÜ 2025
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Webhook",
    "summary": "Webhook implementation for Cetmix Tower",
    "version": "18.0.1.0.1",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "live_test_url": "https://tower.cetmix.com/download",
    "images": ["static/description/banner.png"],
    "author": "Cetmix",
    "license": "AGPL-3",
    "installable": True,
    "depends": ["cetmix_tower_yaml"],
    "data": [
        "security/ir.model.access.csv",
        "views/cx_tower_webhook_authenticator_views.xml",
        "views/cx_tower_webhook_log_views.xml",
        "views/cx_tower_webhook_views.xml",
        "views/cx_tower_variable_views.xml",
        "views/res_config_settings_views.xml",
        "views/menuitems.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
