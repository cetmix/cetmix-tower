# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server Terminal",
    "summary": "Interactive SSH terminal for Cetmix Tower servers",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "depends": ["cetmix_tower_server", "bus"],
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_terminal_session_security.xml",
        "views/cx_tower_server_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cetmix_tower_server_terminal/static/src/terminal/*.js",
            "cetmix_tower_server_terminal/static/src/terminal/*.scss",
            "cetmix_tower_server_terminal/static/src/terminal/*.xml",
        ],
        # Loaded on demand by the terminal client action, so that xterm.js is not
        # part of the backend bundle of every page.
        "cetmix_tower_server_terminal.assets_xterm": [
            "cetmix_tower_server_terminal/static/lib/xterm/xterm.css",
            "cetmix_tower_server_terminal/static/lib/xterm/xterm.js",
            "cetmix_tower_server_terminal/static/lib/xterm/addon-fit.js",
            "cetmix_tower_server_terminal/static/lib/xterm/addon-search.js",
        ],
    },
}
