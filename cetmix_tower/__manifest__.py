# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower",
    "summary": "Odoo SAAS Server Application Management",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "live_test_url": "https://tower.cetmix.com/download",
    "images": ["static/description/banner.png"],
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "depends": [
        "cetmix_tower_server",
        "cetmix_tower_server_queue",
        "cetmix_tower_git",
        "cetmix_tower_webhook",
    ],
}
