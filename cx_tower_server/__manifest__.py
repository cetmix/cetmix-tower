# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server Management",
    "summary": "Manage remote servers directly from Odoo",
    "version": "14.0.1.0.0",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "external_dependencies": {
        "python": ["paramiko"],
        "bin": [],
    },
    "depends": [
        "base",
    ],
    "data": [
        "security/cx_tower_server_security.xml",
        "security/ir.model.access.csv",
        # "templates/assets.xml",
        # "views/report_name.xml",
        "views/cx_tower_server.xml",
        # "wizards/wizard_model_view.xml",
    ],
    # "demo": [
    #     "demo/assets.xml",
    #     "demo/res_partner_demo.xml",
    # ],
}
