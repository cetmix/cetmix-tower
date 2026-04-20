{
    "name": "Cetmix Tower Server Monitor",
    "version": "18.0.1.0.0",
    "category": "Tower",
    "summary": "Resource monitoring (RAM, SSD, CPU) for Tower servers.",
    "author": "Cetmix, Crumges",
    "website": "https://tower.cetmix.com",
    "depends": [
        "cetmix_tower_server",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "views/cx_tower_server_views.xml",
        "views/cx_tower_server_metrics_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "cetmix_tower_server_monitor/static/src/css/dashboard.css",
            "cetmix_tower_server_monitor/static/src/js/dashboard.js",
            "cetmix_tower_server_monitor/static/src/xml/dashboard.xml",
        ],
    },
    "installable": True,
    "license": "AGPL-3",
}
