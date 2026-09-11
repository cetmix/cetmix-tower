{
    "name": "Cetmix Tower SSH Proxy",
    "summary": "Connect to Tower servers through SSH jump/proxy servers",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix, Dinar Gabbasov",
    "license": "AGPL-3",
    "installable": True,
    "application": False,
    "depends": [
        "cetmix_tower_server",
    ],
    "data": [
        "views/cx_tower_server_views.xml",
        "views/cx_tower_server_template_views.xml",
        "wizards/cx_tower_server_template_create_wizard_views.xml",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
