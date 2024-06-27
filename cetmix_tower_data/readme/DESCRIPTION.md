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
      # Standard server variables
      software_image: "{{ software_instance }}:version-1.0"
      software_instance: "myname-software"

      # Software server variables

variables:
  # Standard server variables
  software_image: ""
  software_instance: ""

  # Software server variables

  # Software variables with READONLY global value
  software_path: "{{ software_root }}/{{ software_instance }}"
  software_root: "{{ tower_root }}/software"

  # Software -variables with NOUPDATE global value
