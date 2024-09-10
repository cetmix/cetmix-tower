[Cetmix Tower](http://cetmix.com/tower) offers a streamlined solution for managing remote servers via SSH or API calls directly from [Odoo](https:/odoo.com).
It is designed for versatility across different operating systems and software environments, providing a practical option for those looking to manage servers without getting tied down by vendor or technology constraints.

# Why Cetmix Tower?

- **Open Source:** [Cetmix Tower](http://cetmix.com/tower) is distributed under the AGPL-3 license
- **Odoo Integration:** Benefit from [Odoo](https:/odoo.com) ecosystem for server management tasks, like deploying servers in response to specific Odoo-triggered events
- **Extendability:** Build your own [Odoo](https:/odoo.com) modules using [Cetmix Tower](http://cetmix.com/tower) to implement your custom features
- **Beyond Odoo:** While optimized for Odoo, Cetmix Tower can manage virtually any instance
- **Flexibility:** Use Cetmix Tower alongside other management methods without restriction, ensuring you're not limited to a single vendor
- **Self-Hosting:** Deploy Cetmix Tower on your own infrastructure for full control over your server management.
- **Broad Compatibility:** Execute any software that's manageable via shell commands or API. From Docker or Kubernetes to direct OS package installations

# Server Management

- Variable based flexible configuration
- Create servers using pre-defined templates

# Connectivity

- Password and key based authentication for outgoing SSH connections
- Built-in support of the Python [requests library](https://pypi.org/project/requests/) for outgoing API calls

# Commands

- Execute SSH commands on remote servers
- Run Python code on the Tower Odoo server
- Run Flight Plan from command
- Render commands using variables
- Secret keys for private data storage

# Flight Plans

- Execute multiple commands in a row
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
- This module depends on the [OCA](http://odoo-community.org) free [Web Notify](https://github.com/OCA/web/tree/14.0/web_notify) module. Please ensure it is installed in your system for your Odoo version
- For additional details, visit our website [cetmix.com](https://cetmix.com)
