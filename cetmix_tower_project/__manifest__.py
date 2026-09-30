# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower Project",
    "summary": "Link Cetmix Tower Jets to Odoo Project tasks",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": [
        "project",
        "cetmix_tower_server",
    ],
    "data": [
        "views/cx_tower_jet_views.xml",
        "views/project_task_views.xml",
    ],
}
