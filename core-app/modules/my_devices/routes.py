from flask import render_template
from flask_login import login_required, current_user
from models.inventory import Handover, PersonRef
from auth.permissions import require_permission
from . import my_devices_bp

@my_devices_bp.route('/')
@login_required
@require_permission('my_devices.access')
def index():
    # Find PersonRef for current user
    person = PersonRef.query.filter_by(ldap_username=current_user.username).first()
    
    handovers = []
    if person:
        # Get active handovers (return_date is None)
        handovers = Handover.query.filter_by(
            receiver_id=person.id,
            return_date=None
        ).all()
        
    return render_template('my_devices/index.html', handovers=handovers)
