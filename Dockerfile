# Bakes the addon into the official Odoo image so a server (Coolify) can build
# and run it straight from git, with no bind mount.
#
# The addon lives in /opt/odoo-addons, not /mnt/extra-addons: the official image
# declares /mnt/extra-addons as a VOLUME, and a volume can hide files baked into
# the image. docker-compose.prod.yml adds /opt/odoo-addons to --addons-path.
FROM odoo:18

COPY --chown=odoo:odoo . /opt/odoo-addons/my_module
