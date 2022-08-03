# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server Management",
    "summary": "Manage remote servers directly from Odoo",
    "version": "14.0.0.1.7",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "LGPL-3",
    "application": True,
    "installable": True,
    "external_dependencies": {
        "python": ["paramiko", "scp"],
        "bin": [],
    },
    "depends": [
        "base",
    ],
    "data": [
        "security/cx_tower_server_security.xml",
        "security/ir.model.access.csv",
        "data/ir_actions_server.xml",
        "views/cx_tower_server_view.xml",
        "views/cx_tower_os_view.xml",
        "views/cx_tower_tag_view.xml",
        "views/cx_tower_interpreter_view.xml",
        "views/cx_tower_variable_view.xml",
        "views/cx_tower_variable_value_view.xml",
        "views/cx_tower_command_view.xml",
        "views/cx_tower_key_view.xml",
        "views/menuitems.xml",
        "wizards/cx_tower_command_execute_wizard_view.xml",
    ],
    # "demo": [
    #     "demo/assets.xml",
    #     "demo/res_partner_demo.xml",
    # ],
}
