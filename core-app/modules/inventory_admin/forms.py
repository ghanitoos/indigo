from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, DateField, HiddenField
from wtforms.validators import DataRequired, Optional
from datetime import date


class DeviceForm(FlaskForm):
    inventory_number = StringField('Inventarnummer', validators=[Optional()])
    device_type = StringField('Gerätetyp', validators=[DataRequired()])
    model_name = StringField('Modell', validators=[DataRequired()])
    serial_number = StringField('Seriennummer', validators=[Optional()])
    scope = StringField('Verwendungszweck', validators=[Optional()])
    notes = TextAreaField('Notizen', validators=[Optional()])
    is_active = BooleanField('Aktiv', default=True)


class HandoverForm(FlaskForm):
    # Receiver
    receiver_id = HiddenField('Receiver ID', validators=[Optional()])
    receiver_ldap_username = HiddenField('Receiver LDAP Username', validators=[Optional()])
    receiver_first_name = StringField('Vorname (Empfänger)', validators=[DataRequired()])
    receiver_last_name = StringField('Nachname (Empfänger)', validators=[DataRequired()])
    receiver_department = StringField('Abteilung (Empfänger)', validators=[Optional()])

    # Giver
    giver_id = HiddenField('Giver ID', validators=[Optional()])
    giver_ldap_username = HiddenField('Giver LDAP Username', validators=[Optional()])
    # Giver name fields are optional because the giver can be identified by
    # LDAP username (prefilled from current_user). Making these optional
    # prevents form validation from blocking when inputs are rendered hidden.
    giver_first_name = StringField('Vorname (Geber)', validators=[Optional()])
    giver_last_name = StringField('Nachname (Geber)', validators=[Optional()])
    giver_department = StringField('Abteilung (Geber)', validators=[Optional()])

    handover_date = DateField('Übergabedatum', format='%Y-%m-%d', validators=[DataRequired()])
    notes = TextAreaField('Notizen', validators=[Optional()])


class ReturnForm(FlaskForm):
    # Default return date should be today when the form is displayed empty.
    # Keep validators Optional so a return can be recorded without a date in some flows.
    return_date = DateField('Rückgabedatum', format='%Y-%m-%d', validators=[Optional()], default=date.today)
    notes = TextAreaField('Notizen', validators=[Optional()])
