from datetime import date
from extensions import db
from models.base import BaseModel

class Device(BaseModel):
    __tablename__ = 'inventory_devices'

    id = db.Column(db.Integer, primary_key=True)
    inventory_number = db.Column(db.String(50), unique=True, nullable=False)
    device_type = db.Column(db.String(100), nullable=False)
    model_name = db.Column(db.String(200), nullable=False)
    serial_number = db.Column(db.String(200), nullable=True)
    scope = db.Column(db.String(100), nullable=True) # e.g. "Employee Laptop", "Pool Device"
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    # When a device is discarded/broken, record the date and optional notes
    discarded_at = db.Column(db.Date, nullable=True)
    discarded_notes = db.Column(db.Text, nullable=True)

    # Relationships
    handovers = db.relationship('Handover', foreign_keys='Handover.device_id', backref='device', lazy='dynamic')

    def __repr__(self):
        return f'<Device {self.inventory_number}>'

class PersonRef(BaseModel):
    __tablename__ = 'inventory_person_refs'

    id = db.Column(db.Integer, primary_key=True)
    ldap_username = db.Column(db.String(150), nullable=True, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<PersonRef {self.first_name} {self.last_name}>'

class Handover(BaseModel):
    __tablename__ = 'inventory_handovers'

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('inventory_devices.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('inventory_person_refs.id'), nullable=False)
    giver_id = db.Column(db.Integer, db.ForeignKey('inventory_person_refs.id'), nullable=False)
    
    handover_date = db.Column(db.Date, nullable=False, default=date.today)
    return_date = db.Column(db.Date, nullable=True)
    protocol_number = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    receiver = db.relationship('PersonRef', foreign_keys=[receiver_id], backref='received_handovers')
    giver = db.relationship('PersonRef', foreign_keys=[giver_id], backref='given_handovers')

    def __repr__(self):
        return f'<Handover {self.protocol_number}>'

class InventorySettings(BaseModel):
    __tablename__ = 'inventory_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<InventorySettings {self.key}>'
