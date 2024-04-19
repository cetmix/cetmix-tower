# Copyright 2024 Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': 'Cetmix Tower Template Odoo',
    'description': """
        Cetmix Tower Odoo deployment template""",
    'version': '14.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Cetmix',
    'website': 'https://cetmix.com',
    'depends': ['cetmix_tower_server'],
    
    'data': [ "data/cx_tower_variable_data.xml",
    ],
    'demo': [
    ],
}
