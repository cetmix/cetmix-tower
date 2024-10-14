# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server YAML",
    "summary": "Cetmix Tower YAML export/import",
    "version": "14.0.1.0.0",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["cetmix_tower_server"],
    "external_dependencies": {"python": ["pyyaml"]},
    "data": [
        "views/cx_tower_command_view.xml",
        "views/cx_tower_file_template_view.xml",
    ],
}
