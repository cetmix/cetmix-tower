
## Create a new Server from a Server Template

- Go to the `Cetmix Tower/Servers/Templates` menu and select a [Server Template](CONFIGURE.md/#configure-a-server-template)
- Click "Create Server" button. A pop-up wizard will open with server parameters populated from the template
- Put the new server name, check the parameters and click "Confirm" button
- New server will be created
- If a [Flight Plan](CONFIGURE.md/#configure-a-flight-plan) is defined in the server template it will be automatically executed after a new server is created

You can also create a new server from template from code using a designated `create_server_from_template` function of the `cx.tower.server.template` model.
This function takes the following arguments:

``` python
- template_reference (Char): Server template reference
- server_name (Char): Name of the new server
- **kwargs:
  - partner (res.partner(), optional): Partner this server belongs to.
  - ipv4 (Char, optional): IP v4 address. Defaults to None.
  - ipv6 (Char, optional): IP v6 address. Must be provided in case IP v4 is not. Defaults to None.
  - ssh_password (Char, optional): SSH password. Defaults to None. Defaults to None.
  - ssh_private_key_value (Char, optional): SSH private key content.
  - ssh_private_key_value (cx.tower.key(), optional): SSH private key record. Defaults to None.
  - configuration_variables (Dict, optional): Custom configuration variable.
    Following format is used:
      'variable_reference': 'variable_value_char'
      eg:
      {'branch': 'prod', 'odoo_version': '16.0'}
```

Here is a short example of an Odoo automated action that creates a new server when a Sales Order is confirmed:

![Automatic action](../static/description/images/server_from_template_auto_action.png)

```python
for record in records:
  
  # Check confirmed orders
  if record.state == "sale":
    params = {
      "ip_v4_address": "host.docker.internal",
      "ssh_port": 2222,
      "ssh_username": "pepe",
      "ssh_password": "frog",
      "ssh_auth_mode": "p",
      "configuration_variables": {
        "odoo_version": "16.0"
        },
    }
    
    # Create a new server from template with the 'demo_template' reference 
    env["cetmix.tower"].server_create_from_template(
      template_reference="demo_template",
      server_name=record.name,
      **params
      )
    
```

## Run a Command

- Select a server in the list view or open a server form view
- Open the `Actions` menu and click `Execute Command`
- A wizard is opened with the following fields:
  - **Servers**: Servers on which this command will be executed
  - **Tags**: If selected only commands with these tags will be shown
  - **Sudo**: `sudo` option for running this command
  - **Command**: Command to execute
  - **Show shared**: By default only commands available for the selected server(s) are selectable. Activate this checkbox to select any command
  - **Path**: Directory where command will be executed. Important: this field does not support variables! Ensure that user has access to this location even if you run command using sudo.
  - **Code**: Raw command code
  - **Preview**: Command code rendered using server variables.
  **IMPORTANT:** If several servers are selected preview will be rendered for the first one. However during the command execution command code will be rendered for each server separately.

There are two action buttons available in the wizard:

- **Run**. Executes a command using server "run" method and log command result into the "Command Log".
- **Run in wizard**. Executes a command directly in the wizard and show command log in a new wizard window.

You can check command execution logs in the `Cetmix Tower/Commands/Command Logs` menu.
Important! If you want to delete a command you need to delete all its logs manually before doing that.

## Run a Flight Plan

- Select a server in the list view or open a server form view
- Open the `Actions` menu and click `Execute Flight Plan`
- A wizard is opened with the following fields:
  - **Servers**: Servers on which this command will be executed
  - **Tags**: If selected only commands with these tags will be shown
  - **Plan**: Flight plan to execute
  - **Show shared**: By default only flight plans available for the selected server(s) are selectable. Activate this checkbox to select any flight plan
  - **Commands**: Commands that will be executed in this flight plan. This field is read only

  Click the **Run** button to execute a flight plan.

  You can check the flight plan results in the `Cetmix Tower/Commands/Flight Plan Logs` menu.
  Important! If you want to delete a command you need to delete all its logs manually before doing that.

## Check a Server Log

To check a server log:

- Navigate to the `Server Logs` tab on the Server form
- Click on the log **(1)** you would like to check to open in in a pop up window. Or click on the `Open` button **(2)** to open it in the full form view

![Open server log](../static/description/images/server_log_usage_1.png)
- Click the `Refresh` button to update the log. You can also click the `Refresh All` button **(3)** located above the log list in order to refresh all logs at once.
Log output will be displayed in the HTML field below.

![Update server log](../static/description/images/server_log_usage_2.png)

## Using Cetmix Tower in Odoo automation

You can use various Cetmix Tower functions in Odoo automation. Such as server actions, automated actions or scheduled actions.
While you can always call any public function directly most useful helper functions are located in a special abstract model "cetmix.tower".
You can check those functions in the source code in the following file: `models/cetmix_tower.py`
