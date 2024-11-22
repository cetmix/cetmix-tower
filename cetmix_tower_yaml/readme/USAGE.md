## Export into a YAML file

To export data into YAML format:

- Open the record you would like to export.
- On the "YAML" tab click the "Export YAML" button.
- YAML export wizard will open:
  - Activate "Explode Child Records" switch if you want to export data in [exploded mode](#exploded-mode).
  - Click "Generate YAML File" button to save YAML file.
- File download wizard will open:
  - Click on the file name to save YAML file.
  - Click the "Close" button to close the file download wizard.

## Import from a YAML file

To import data from YAML:

- Go to "Cetmix Tower -> Tools -> Import YAML" menu.
- Upload a YAML file and click the "Process" button.
- YAML import wizard will open.
  - If a record that is specified in the YAML file exists, there will be an "Update Existing Record" checkbox available.
  - Uncheck the "Update Existing Record" checkbox if you want to create a new record instead of updating the existing one.
- Click one of the available action buttons:
  - "Update Existing Record" to update the existing record.
  - "Open Existing Record" to open the record that is specified in the YAML file.
  - "Create New Record" to create a new record.

Important things to remember during import:

- If a record that is specified in the YAML file does not exist in Odoo, new record will be created.
- If a record that is specified in the YAML file exists in Odoo and the "Update Existing Record" checkbox is checked, it will be updated with new values from YAML.
- If a record that is specified in the YAML file exists in Odoo and the "Update Existing Record" checkbox is not checked, new record will be created.
- Following model records will be always tried to be resolved and updated even if "Create New Record" action is used:
  - Variables
  - Operating Systems
  - Tags

## Data Export/Import Modes

Data stored in related fields such as One2many, Many2one and Many2many can be handled using two different modes.

### Reference mode

In this mode related record is represented with its reference:

```yaml
file_template_id: my_custom_template
```

In case related record cannot be resolved using provided reference while importing  data from YAML, `Null` value will be assigned instead.

### Exploded mode

In this mode related record is represented as a child YAML structure:

```yaml
file_template_id:
  cetmix_tower_model: file_template
  cetmix_tower_yaml_version: 1
  code: false
  file_name: much_logs.txt
  file_type: text
  keep_when_deleted: false
  name: Very my custom
  note: Hey!
  reference: my_custom_template
  server_dir: /var/log/my/files
  source: server
```

This mode allows to export/import child records together with the parent one.
In case any of the child fields are modified in YAML related record in Odoo will be modified using those values.
In case related record cannot be resolved using child reference while importing data from YAML, new child record will be created in Odoo using YAML values.
