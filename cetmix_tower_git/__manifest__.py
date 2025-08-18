# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Git",
    "summary": "Cetmix Tower Git Management Tools",
    "version": "16.0.1.0.6",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "depends": ["cetmix_tower_yaml"],
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_git_project_security.xml",
        "security/cx_tower_git_source_security.xml",
        "security/cx_tower_git_remote_security.xml",
        "security/cx_tower_git_project_rel_security.xml",
        "security/cx_tower_git_project_file_template_rel_security.xml",
        "views/cx_tower_git_project_views.xml",
        "views/cx_tower_git_source_views.xml",
        "views/cx_tower_git_remote_views.xml",
        "views/cx_tower_file_views.xml",
        "views/cx_tower_file_template_views.xml",
        "views/cx_tower_server_view.xml",
        "views/cx_tower_plan_line_view.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
