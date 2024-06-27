#!/bin/bash
echo "Converting to xml..."
# TOWER
python ./convert_to_xml.py commands ./data/commands.yaml ./data/commands.xml
python ./convert_to_xml.py plans ./data/plans.yaml ./data/plans.xml
python ./convert_to_xml.py variables ./data/variables.yaml ./data/variables.xml
# ODOO
python ./convert_to_xml.py file_templates ../cetmix_tower_data_odoo/data/file_templates.yaml ../cetmix_tower_data_odoo/data/file_templates.xml
python ./convert_to_xml.py commands ../cetmix_tower_data_odoo/data/commands.yaml ../cetmix_tower_data_odoo/data/commands.xml
python ./convert_to_xml.py plans ../cetmix_tower_data_odoo/data/plans.yaml ../cetmix_tower_data_odoo/data/plans.xml
python ./convert_to_xml.py servers ../cetmix_tower_data_odoo/data/servers.yaml ../cetmix_tower_data_odoo/data/servers.xml
python ./convert_to_xml.py variables ../cetmix_tower_data_odoo/data/variables.yaml ../cetmix_tower_data_odoo/data/variables.xml
# POSTGRES
python ./convert_to_xml.py commands ../cetmix_tower_data_postgres/data/commands.yaml ../cetmix_tower_data_postgres/data/commands.xml
python ./convert_to_xml.py plans ../cetmix_tower_data_postgres/data/plans.yaml ../cetmix_tower_data_postgres/data/plans.xml
python ./convert_to_xml.py servers ../cetmix_tower_data_postgres/data/servers.yaml ../cetmix_tower_data_postgres/data/servers.xml
python ./convert_to_xml.py variables ../cetmix_tower_data_postgres/data/variables.yaml ../cetmix_tower_data_postgres/data/variables.xml
# TRAEFIK
python ./convert_to_xml.py commands ../cetmix_tower_data_traefik/data/commands.yaml ../cetmix_tower_data_traefik/data/commands.xml
python ./convert_to_xml.py servers ../cetmix_tower_data_traefik/data/servers.yaml ../cetmix_tower_data_traefik/data/servers.xml
python ./convert_to_xml.py variables ../cetmix_tower_data_traefik/data/variables.yaml ../cetmix_tower_data_traefik/data/variables.xml
echo "Done"
echo "Press any key to close the terminal."
read -n 1 -s -r -p ""