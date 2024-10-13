YAML to XML
Use convert_to_xml.sh

Best practice for variables
---------------------------

All variables should have a global default value.
- The user may change the global value.
- The user may archive the global value.
- The user should NOT delete the global value. Then it will be reset to the global default value.

software_instance name will be used for
- container name
- database name
- directory name

variables:
  # Standard variables
  software_image: "{{ software_instance }}:latest"
  software_instance: "myname-software"
  software_path: "{{ software_root }}/{{ software_instance }}"
  software_root: "{{ tower_root }}/software"
  # Custom -variables
