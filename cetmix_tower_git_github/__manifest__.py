# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Git GitHub",
    "summary": "List GitHub branches, pull requests, and commits on a Git remote",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "images": ["static/description/banner.png"],
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "depends": ["cetmix_tower_git"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/cx_tower_git_github_sync_wizard_views.xml",
        "views/cx_tower_git_repo_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
