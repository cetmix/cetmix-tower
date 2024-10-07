FROM my-odoo:14.0

# Install project related modules as root gi
USER root
RUN python3.10 -m pip install paramiko pyyaml
USER odoo
