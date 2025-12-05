# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Server Queue",
    "summary": "Cetmix Tower asynchronous task execution using 'queue_job'",
    "version": "18.0.1.0.0",
    "development_status": "Beta",
    "category": "Productivity",
    "website": "https://tower.cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "installable": True,
    "auto_install": True,
    "depends": ["cetmix_tower_server", "queue_job"],
    "data": [
        "views/cx_tower_command_log_view.xml",
        "views/cx_tower_file_view.xml",
    ],
}
