# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower AWS",
    "summary": """Cetmix Tower AWS EC2 API integration""",
    "version": "18.0.1.0.1",
    "category": "Productivity",
    "license": "AGPL-3",
    "author": "Cetmix",
    "website": "https://tower.cetmix.com",
    "live_test_url": "https://tower.cetmix.com/download",
    "images": ["static/description/banner.png"],
    "installable": True,
    "external_dependencies": {
        "python": ["boto3"],
    },
    "depends": [
        "cetmix_tower_server",
    ],
    "demo": [
        "demo/demo_data.xml",
    ],
}
