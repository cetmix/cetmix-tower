# Copyright 2025 Cetmix OÜ
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

# Mail is required: its ir.websocket override subscribes the partner channel to the
# bus, so users receive web.refresh_view notifications.

{
    "name": "Web Refresh From Backend",
    "summary": "Refresh frontend views from backend",
    "version": "18.0.1.0.0",
    "category": "Web",
    "license": "LGPL-3",
    "author": "Cetmix",
    "website": "https://tower.cetmix.com",
    "images": ["static/description/banner.png"],
    "depends": ["mail"],
    "assets": {
        "web.assets_backend": [
            "cx_web_refresh_from_backend/static/src/views/utils/get_loaded_record_ids.esm.js",
            "cx_web_refresh_from_backend/static/src/views/list/list_controller_patch.esm.js",
            "cx_web_refresh_from_backend/static/src/views/kanban/kanban_controller_patch.esm.js",
            "cx_web_refresh_from_backend/static/src/views/form/form_controller_patch.esm.js",
        ],
        "web.qunit_suite_tests": [
            "cx_web_refresh_from_backend/static/tests/refresh_from_backend_tests.esm.js",
        ],
    },
    "installable": True,
    "auto_install": False,
}
