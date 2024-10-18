## Data Export/Import

To export data into YAML format:

- Open the record you would like to export
- Copy YAML code from the text field located under the "YAML" tab in the form view.
Activate "Explode" switch if you want to export data in [exploded mode](#exploded-mode)

To import data from YAML:

- Open the record you would like to import
- Insert YAML code from in the text field located under the "YAML" tab in the form view.

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
