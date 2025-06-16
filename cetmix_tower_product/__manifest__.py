# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    "name": "Cetmix Tower Product",
    "summary": "Link Cetmix Tower variables to Odoo product attributes",
    "version": "16.0.1.0.0",
    "category": "Product",
    "website": "https://cetmix.com",
    "author": "Cetmix",
    "license": "AGPL-3",
    "installable": True,
    "depends": [
        "cetmix_tower_server",
        "product",
    ],
    "data": [
        "views/product_attribute_views.xml",
    ],
    # "demo": [
    #     "demo/demo_data.xml",  # Commented for now
    # ],
}
