Cetmix Tower offers a streamlined solution for managing remote servers via SSH directly from Odoo.
This module is designed for versatility across different operating systems and software environments, providing a practical option for those looking to manage servers without getting tied down by vendor or technology constraints.

- **Why Cetmix Tower?**

  - **Open Source:** Cetmix Tower is distributed under the AGPL-3 license.
  - **Flexibility:** Use Cetmix Tower alongside other management methods without restriction, ensuring you're not limited to a single vendor.
  - **Self-Hosting:** Deploy Cetmix Tower on your own infrastructure for full control over your server management.
  - **Broad Compatibility:** Execute any software that's manageable via shell commands, from Docker or Kubernetes to direct OS package installations.
  - **Odoo Integration:** Benefit from Odoo's ecosystem for server management tasks, like deploying servers in response to specific Odoo-triggered events.
  - **Beyond Odoo:** While optimized for Odoo, Cetmix Tower supports a wide range of software applications, offering flexibility in server management tasks.

- **Connectivity**

  - Password and key based authentication when connection to remote server.
  - Server wide variables that can be used for rendering commands.

- **Commands**

  - Execute commands on multiple servers at once.
  - Render commands using variables.
  - Store sensitive information in secret keys that are not visible in command preview.

- **Flight Plans**

  - Execute commands in series.
  - Condition based flow: execute a command based on the previous command result.

- **Files**

  - Download files from remote server using SFTP.
  - Upload files to remote server using SFTP.
  - Manage files using templates.

- **Support and Technical Requirements**

  - This module depends on the [OCA](http://odoo-community.org) free [Web Notify](https://github.com/OCA/web/tree/14.0/web_notify) module. Please ensure it is installed in your system for your Odoo version.
  - Cetmix Tower is designed to be accessible, though some features might require a foundational understanding of server management principles.
  - We offer dedicated support to help with any custom setup needs or questions that arise.
  - For additional details, visit our website [cetmix.com](https://cetmix.com).
