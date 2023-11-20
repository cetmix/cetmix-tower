# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server Management",
    "summary": "Manage remote servers directly from Odoo",
    "version": "14.0.0.3.4",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "external_dependencies": {
        "python": ["paramiko"],
        "bin": [],
    },
    "depends": [
        "mail",
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
        "views/cx_tower_plan_view.xml",
        "views/cx_tower_plan_line_view.xml",
        "views/cx_tower_command_log_view.xml",
        "views/cx_tower_plan_log_view.xml",
        "views/cx_tower_key_view.xml",
        "views/menuitems.xml",
        "wizards/cx_tower_command_execute_wizard_view.xml",
        "wizards/cx_tower_plan_execute_wizard_view.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
