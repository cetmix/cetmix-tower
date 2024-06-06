YAML to XML
Use convert_to_xml.sh

Best practice for variables
---------------------------

server:
  myserver:
    variables:
      software_image_name: "{{ software_instance_name }}"
      software_image_tag: "1.0"
      software_instance_name: "myname-software"

variables:
  software_image_name: ""
  software_image_tag: ""
  software_instance_name: ""

  software_container: "{{ software_instance_name }}-{{ software_image_version }}"
  software_image: "{{ software_image_name }}:{{ software_image_version }}"
  software_instance_path: "{{ software_root }}/{{ software_instance_name }}"
  software_root: "{{ tower_root }}/software"
