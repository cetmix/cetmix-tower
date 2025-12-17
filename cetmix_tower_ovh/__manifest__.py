# Copyright 2024 Cetmix OÜ
# Copyright 2025 Giovanni Serra <giovanni@gslab.it>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Cetmix Tower OVH",
    "summary": """Cetmix Tower OVH API integration""",
    "version": "18.0.1.0.1",
    "category": "Productivity",
    "license": "AGPL-3",
    "author": "Cetmix, Giovanni Serra",
    "maintainers": ["GSLabIt"],
    "website": "https://tower.cetmix.com",
    "images": ["static/description/banner.png"],
    "application": False,
    "installable": True,
    "demo": [
        "demo/demo_data.xml",
    ],
    "external_dependencies": {"python": ["ovh"]},
    "depends": [
        "cetmix_tower_server",
    ],
}
