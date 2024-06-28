# Copyright 2024 Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower Data - Traefik",
    "summary": """
        Cetmix Tower standard Traefik deployment""",
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "Loym",
    "website": "https://www.loym.com",
    "depends": ["cetmix_tower_data"],
    "data": [
        "data/cx_tower_tag_data.xml",
        "data/commands.xml",
        "data/variables.xml",
        "data/servers.xml",
    ],
    "demo": [],
}
