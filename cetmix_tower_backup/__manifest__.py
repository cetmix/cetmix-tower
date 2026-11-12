# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Backup",
    "summary": "Durable Jet backups and restore into new Jets",
    "version": "18.0.1.0.0",
    "category": "Productivity",
    "license": "AGPL-3",
    "author": "Cetmix",
    "website": "https://tower.cetmix.com",
    "depends": ["cetmix_tower_yaml"],
    "application": False,
    "installable": True,
    "data": [
        "security/ir.model.access.csv",
        "security/cx_tower_backup_wizard_access_rules.xml",
        "data/ir_cron.xml",
        "wizards/cx_tower_backup_wizard_views.xml",
        "views/cx_tower_backup_template_views.xml",
        "views/cx_tower_backup_views.xml",
        "views/cx_tower_backup_inherited_views.xml",
    ],
    "demo": ["demo/cx_tower_backup_demo.xml"],
}
