YAML to XML
Use convert_to_xml.sh

Best practice for variables
---------------------------

server:
  myserver:
    variables:
      # Standard server variables
      software_image_name: "{{ software_instance_name }}:version-1.0"
      software_instance_name: "myname-software"

      # Software server variables

variables:
  # Standard server variables
  software_image_name: ""
  software_instance_name: ""

  # Software server variables

  # Software variables with READONLY global value
  software_container_name: "{{ software_instance_name }}"
  software_instance_path: "{{ software_root }}/{{ software_instance_name }}"
  software_root: "{{ tower_root }}/software"

  # Software -variables with NOUPDATE global value
