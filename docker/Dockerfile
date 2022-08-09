FROM odoo:14.0
USER root

# Install git
RUN apt-get update && \
    apt-get install -qy --no-install-recommends \
    git build-essential python3-pip python3-dev

RUN pip3 install --upgrade pip && pip install paramiko scp

# Set default user when running the container
USER odoo

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
