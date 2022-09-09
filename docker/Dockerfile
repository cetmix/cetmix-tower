FROM odoo:14.0
ARG ODOO_BRANCH=14.0
ARG TOWER_BRANCH=14.0-dev
ARG ODOO_ADDONS_TMP_LOCATION=/tmp/odoo-addons
ARG ODOO_ADDONS_LOCATION=/opt/odoo/extra-addons
ARG GITHUB_TOKEN=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

USER root
WORKDIR /opt/odoo-addons

# Install git
RUN apt-get update && \
    apt-get install -qy --no-install-recommends \
    git build-essential python3-pip python3-dev

RUN pip3 install --upgrade pip && pip install paramiko scp

# Clone third party addons
WORKDIR ${ODOO_ADDONS_TMP_LOCATION}
RUN git config --global alias.solo 'clone --depth 1 --single-branch -b' \
    && git solo ${TOWER_BRANCH} https://${GITHUB_TOKEN}:x-oauth-basic@github.com/cetmix/cetmix-tower.git

# Make default
RUN find . -type d -maxdepth 2 -exec setuptools-odoo-make-default --addons-dir={} --odoo-version-override=${ODOO_BRANCH} \;
# Build requirements
RUN find . -type d -maxdepth 2 -exec setuptools-odoo-get-requirements --addons-dir={} --output={}/requirements.txt \;

# Install requirements
RUN find ./ -mindepth 0 -name requirements.txt  -exec  cat {} > all_requirements.txt + \
    && pip3 install -r all_requirements.txt

# Move all modules to the final destination
RUN mkdir -p ${ODOO_ADDONS_LOCATION} && \
    find . -mindepth 2 -maxdepth 2 -type d -not \( -name '.*' -o -name 'setup' \) -exec mv -f {} ${ODOO_ADDONS_LOCATION} \; \
    && ls -la ${ODOO_ADDONS_LOCATION} \
    && chown -R odoo ${ODOO_ADDONS_LOCATION} \
    && rm -rf ${ODOO_ADDONS_TMP_LOCATION}

# Let's go!
USER odoo
