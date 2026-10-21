# Copyright 2026 Cetmix OÜ
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Web Widget Autocomplete",
    "summary": "Autocomplete widget",
    "version": "18.0.1.0.0",
    "category": "Hidden",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "LGPL-3",
    "images": ["static/description/banner.png"],
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "cx_web_widget_autocomplete/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "cx_web_widget_autocomplete/static/tests/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
