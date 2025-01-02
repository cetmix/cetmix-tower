# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Git",
    "summary": "Cetmix Tower Git Management Tools",
    "version": "14.0.1.0.0",
    "category": "Productivity",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["cetmix_tower_yaml"],
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_git_project_security.xml",
        "security/cx_tower_git_source_security.xml",
        "security/cx_tower_git_remote_security.xml",
        "security/cx_tower_git_project_rel_security.xml",
        "views/cx_tower_git_project_views.xml",
        "views/cx_tower_git_source_views.xml",
        "views/cx_tower_git_remote_views.xml",
        "views/cx_tower_file_views.xml",
        "views/cx_tower_server_view.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
