import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-cetmix-cetmix-tower",
    description="Meta package for cetmix-cetmix-tower Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-cetmix_tower_server',
        'odoo14-addon-cetmix_tower_server_queue',
        'odoo14-addon-cetmix_tower_server_yaml',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 14.0',
    ]
)
