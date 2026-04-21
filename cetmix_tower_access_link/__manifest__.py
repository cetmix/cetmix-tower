# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Access Link",
    "version": "18.0.1.0.0",
    "category": "Tower",
    "summary": "Manage quick access links for Cetmix Tower jets.",
    "author": "Cetmix",
    "website": "https://tower.cetmix.com",
    "license": "AGPL-3",
    "depends": [
        "cetmix_tower_server",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/cx_tower_access_template_views.xml",
        "views/cx_tower_jet_template_views.xml",
        "views/cx_tower_jet_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": False,
}
