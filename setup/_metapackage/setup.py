import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-cetmix-cetmix-tower",
    description="Meta package for cetmix-cetmix-tower Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-cetmix_tower>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_aws>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_git>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_ovh>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_server>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_server_notify_backend>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_server_queue>=16.0dev,<16.1dev',
        'odoo-addon-cetmix_tower_yaml>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
