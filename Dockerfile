# Bakes the addon into the official Odoo image so a server (Coolify) can build
# and run it straight from git, with no bind mount.
FROM odoo:18

COPY --chown=odoo:odoo . /mnt/extra-addons/my_module
