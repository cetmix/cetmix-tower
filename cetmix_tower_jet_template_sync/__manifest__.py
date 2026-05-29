# Copyright (C) 2026 Crumges
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower: Jet Template Sync",
    "summary": "Automatically propagates variables, logs, waypoints, and dependencies from template to jets on creation and provides a sync button",
    "version": "18.0.1.0.0",
    "category": "DevOps",
    "author": "Crumges",
    "license": "AGPL-3",
    "installable": True,
    "depends": [
        "cetmix_tower",
    ],
    "data": [
        "views/cx_tower_jet_template_views.xml",
        "views/cx_tower_jet_views.xml",
    ],
}
