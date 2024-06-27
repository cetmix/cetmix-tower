YAML to XML
Use convert_to_xml.sh

Best practice for variables
---------------------------

software_instance name will be used for
- container name
- database name
- directory name

server:
  myserver:
    variables:
      # Standard variables
      software_image: "{{ software_instance }}:version-1.0"
      software_instance: "myname-software"

      # Custom variables

variables:
  # Standard variables - non-empty global values are READONLY.
  software_image: ""
  software_instance: ""
  software_path: "{{ software_root }}/{{ software_instance }}"
  software_root: "{{ tower_root }}/software"

  # Custom -variables - non-empty global values are installed once, NO UPDATE.
