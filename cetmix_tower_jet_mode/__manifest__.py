# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Jet Mode",
    "version": "18.0.1.0.0",
    "category": "Tower",
    "summary": "Configure modes/profiles of configuration variables and "
    "lifecycle actions for Jet Templates and Jets.",
    "author": "Cetmix",
    "website": "https://tower.cetmix.com",
    "license": "AGPL-3",
    "depends": [
        "cetmix_tower_server",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/cx_tower_jet_template_views.xml",
        "views/cx_tower_jet_views.xml",
    ],
    "demo": [
        "demo/cx_tower_jet_mode_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cetmix_tower_jet_mode/static/src/css/jet_mode.css",
        ],
    },
    "installable": True,
    "application": False,
}
