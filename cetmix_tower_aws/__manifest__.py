# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower Aws",
    "summary": """Cetmix Tower AWS EC2 API integration""",
    "version": "14.0.1.0.0",
    "category": "Productivity",
    "license": "AGPL-3",
    "author": "Cetmix OÜ",
    "website": "https://cetmix.com",
    "application": True,
    "installable": True,
    "external_dependencies": {
        "python": ["boto3"],
        "bin": [],
    },
    "depends": [
        "cetmix_tower_server",
        "cetmix_tower_yaml",
    ],
    "data": [],
    "demo": [],
}
