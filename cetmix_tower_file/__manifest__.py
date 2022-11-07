# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower File Management",
    "summary": "Manage File in your remote servers directly from Odoo",
    "version": "14.0.0.0.0",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "external_dependencies": {
        "python": [],
        "bin": [],
    },
    "depends": [
        "cetmix_tower_server",
    ],
    "data": [
        "data/ir_cron.xml",
        "security/ir.model.access.csv",
        "views/cx_tower_file_template_view.xml",
        "views/cx_tower_file_view.xml",
        "views/cx_tower_server_view.xml",
        "views/menuitems.xml",
    ],
    "demo": [
        "demo/cx_tower_file_template.xml",
        "demo/cx_tower_file.xml",
    ],
}
