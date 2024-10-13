## TOWER

Execute flight plan
- Tower - Init

## TRAEFIK

Copy template
Set variables
Execute Command
- Traefik - Create / Run container

## POSTGRES

Copy template
Set variables
Execute command
- Postgres - Create data directory
- Postgres - Create / Run container

## ODOO

Copy template
Set variables
   - odoo_docker_gid = 999 (docker)
   - odoo_docker_uid = 101
Execute command
- Create instance directories
- Set ownership on directories
- Custom command: chmod 775 {{ odoo_instance_config_path }}
Create file
- Source: Tower
- Template: Odoo Config
- Server:
- Button: Push to server
Execute command
- Odoo - Create / Run container (with odoo_args)
Browser
- Check that it works
Set variables
- Delete the odoo_args line
