# Copyright 2024 Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower Data - Postgres",
    "summary": """
        Cetmix Tower standard PostreSQL deployment""",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "Cetmix, Loym",
    "website": "https://cetmix.com",
    "depends": ["cetmix_tower_data"],
    "data": [
        "data/commands.xml",
        "data/plans.xml",
        "data/variables.xml",
        "data/servers.xml",
    ],
    "demo": [],
}
