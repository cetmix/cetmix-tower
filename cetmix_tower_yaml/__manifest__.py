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
        "security/cetmix_tower_yaml_groups.xml",
        "security/ir.model.access.csv",
        "views/cx_tower_command_view.xml",
        "views/cx_tower_file_template_view.xml",
        "views/cx_tower_plan_view.xml",
        "views/cx_tower_server_template_view.xml",
        "wizards/cx_tower_yaml_export_wiz.xml",
        "wizards/cx_tower_yaml_export_wiz_download.xml",
        "wizards/cx_tower_yaml_import_wiz_upload.xml",
        "wizards/cx_tower_yaml_import_wiz.xml",
        "views/menuitems.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
