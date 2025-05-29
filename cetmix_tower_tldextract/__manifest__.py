# Copyright 2025 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower TLDExtract",
    "summary": """Provides wrapped tldextract for tower modules""",
    "version": "14.0.1.0.0",
    "category": "Productivity",
    "license": "AGPL-3",
    "author": "Cetmix",
    "website": "https://cetmix.com",
    "application": False,
    "installable": True,
    "external_dependencies": {"python": ["tldextract"]},
    "depends": [
        "cetmix_tower_server",
    ],
}
