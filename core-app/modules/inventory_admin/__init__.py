from flask import Blueprint

inventory_admin_bp = Blueprint(
    'inventory_admin',
    __name__,
    template_folder='templates',
    url_prefix='/inventory-admin'
)

from . import routes
