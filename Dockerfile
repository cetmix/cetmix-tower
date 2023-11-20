FROM my-odoo:14.0

# Install project related modules
RUN python3.10 -m pip install paramiko
