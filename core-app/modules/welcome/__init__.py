from flask import Blueprint

welcome_bp = Blueprint('welcome', __name__, template_folder='templates', static_folder='static')

from . import routes  # noqa
