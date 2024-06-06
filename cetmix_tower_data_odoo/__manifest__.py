# Copyright 2024 Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower Data - Odoo",
    "summary": "Cetmix Tower standard Odoo deployment",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "Cetmix, Loym",
    "website": "https://cetmix.com",
    "depends": ["cetmix_tower_data_postgres"],
    "data": [
        "data/cx_tower_tag_data.xml",
        "data/commands.xml",
        "data/file_templates.xml",
        "data/plans.xml",
        "data/variables.xml",
        "data/servers.xml",
    ],
    "demo": [],
}
