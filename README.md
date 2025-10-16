
<!-- /!\ Non OCA Context : Set here the badge of your runbot / runboat instance. -->
[![Runboat](https://img.shields.io/badge/runboat-Try%20me-875A7B.png)](https://testit.cetmix.com/webui/builds.html?repo=cetmix/cetmix-tower&target_branch=16.0)
[![Pre-commit Status](https://github.com/cetmix/cetmix-tower/actions/workflows/pre-commit.yml/badge.svg?branch=16.0)](https://github.com/cetmix/cetmix-tower/actions/workflows/pre-commit.yml?query=branch%3A16.0)
[![Build Status](https://github.com/cetmix/cetmix-tower/actions/workflows/test.yml/badge.svg?branch=16.0)](https://github.com/cetmix/cetmix-tower/actions/workflows/test.yml?query=branch%3A16.0)
[![codecov](https://codecov.io/gh/cetmix/cetmix-tower/branch/16.0/graph/badge.svg)](https://codecov.io/gh/cetmix/cetmix-tower)
<!-- /!\ Non OCA Context : Set here the badge of your translation instance. -->

<!-- /!\ do not modify above this line -->

![Banner](https://github.com/cetmix/cetmix-tower/blob/5ff7c0aafe22db6686d0919cc560f7f8a0fe7cd7/cetmix_tower_server/static/description/banner.png)

[Cetmix Tower](http://cetmix.com/tower) offers a streamlined solution for managing remote servers via SSH or API calls directly from [Odoo](https://odoo.com).
It is designed for versatility across different operating systems and software environments, providing a practical option for those looking to manage servers without getting tied down by vendor or technology constraints.

# Why Cetmix Tower?

- **Easy to use:** Regular users can perform actions directly from the Odoo web interface
- **Flexible and configurable:** Technical people can create complex configurations and build powerful automation scenarios using configuration variables and flight plans
- **Odoo powered:** Build everything directly in Odoo, integrate with Odoo automation seamlessly
- **Beyond Odoo:** While optimized for Odoo, Cetmix Tower can manage virtually any instance
- **No techology boundaries:** Docker? Kubernetes? Or maybe just bare shell scipts? You can use what you like
- **Self hosted:** You can run Cetmix Tower directly on your own server
- **Open Source:** [Cetmix Tower](http://cetmix.com/tower) is distributed under the AGPL-3 license

# Server Management

- Variable based flexible configuration
- Create servers using pre-defined templates

# Connectivity

- Password and key based authentication for outgoing SSH connections
- Built-in support of the Python [requests library](https://pypi.org/project/requests/) for outgoing API calls

# Commands

- Run SSH commands on remote servers
- Run Python code on the Tower Odoo server
- Run Flight Plan from command
- Render commands using variables
- Secret keys for private data storage

# Flight Plans

- Run multiple commands in a row
- Condition based flow:
  - Based on condition using [Python syntax](https://www.w3schools.com/python/python_syntax.asp)
  - Based on the previous command exit code

# Files

- Download files from remote server using SFTP
- Upload files to remote server using SFTP
- Support for `text` and `binary` file format
- Manage files using pre-defined file templates

# Support and Technical Requirements

- Cetmix Tower with usability and simplicity in mind, though some features might require a foundational understanding of server management principles
- We offer dedicated support to help with any custom setup needs or questions that may arise
- This module depends on the [OCA](http://odoo-community.org) free [Web Notify](https://github.com/OCA/web/tree/16.0/web_notify) module. Please ensure it is installed in your system for your Odoo version
- For additional details, visit our website [cetmix.com](https://cetmix.com)
Cetmix Tower

<!-- /!\ do not modify below this line -->

<!-- prettier-ignore-start -->

[//]: # (addons)

Available addons
----------------
addon | version | maintainers | summary
--- | --- | --- | ---
[cetmix_tower](cetmix_tower/) | 16.0.2.0.0 |  | Odoo SAAS Server Application Management
[cetmix_tower_aws](cetmix_tower_aws/) | 16.0.1.1.0 |  | Cetmix Tower AWS EC2 API integration
[cetmix_tower_git](cetmix_tower_git/) | 16.0.1.0.7 |  | Cetmix Tower Git Management Tools
[cetmix_tower_ovh](cetmix_tower_ovh/) | 16.0.1.0.0 | <a href='https://github.com/GSLabIt'><img src='https://github.com/GSLabIt.png' width='32' height='32' style='border-radius:50%;' alt='GSLabIt'/></a> | Cetmix Tower OVH API integration
[cetmix_tower_server](cetmix_tower_server/) | 16.0.2.0.5 |  | Manage servers and applications from Odoo
[cetmix_tower_server_notify_backend](cetmix_tower_server_notify_backend/) | 16.0.1.1.0 |  | Backend notifications for Cetmix Tower
[cetmix_tower_server_queue](cetmix_tower_server_queue/) | 16.0.1.1.3 |  | Cetmix Tower asynchronous task execution using 'queue_job'
[cetmix_tower_webhook](cetmix_tower_webhook/) | 16.0.1.0.2 |  | Webhook implementation for Cetmix Tower
[cetmix_tower_yaml](cetmix_tower_yaml/) | 16.0.2.0.0 |  | Cetmix Tower YAML export/import

[//]: # (end addons)

<!-- prettier-ignore-end -->

## Licenses

This repository is licensed under [AGPL-3.0](LICENSE).

However, each module can have a totally different license, as long as they adhere to Cetmix
policy. Consult each module's `__manifest__.py` file, which contains a `license` key
that explains its license.

----
<!-- /!\ Non OCA Context : Set here the full description of your organization. -->
