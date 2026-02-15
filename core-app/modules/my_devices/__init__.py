from flask import Blueprint

my_devices_bp = Blueprint(
    'my_devices',
    __name__,
    template_folder='templates',
    url_prefix='/my-devices'
)

from . import routes
