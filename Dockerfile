FROM my-odoo:14.0

# Install project related modules
RUN python3.7 -m pip install paramiko
