from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, SelectMultipleField, SubmitField
from wtforms.validators import DataRequired, Length

class RoleForm(FlaskForm):
    name = StringField('Role Name', validators=[DataRequired(), Length(min=2, max=50)])
    description = StringField('Description', validators=[Length(max=255)])
    permissions = SelectMultipleField('Permissions', coerce=int)
    submit = SubmitField('Save Role')

class UserRoleForm(FlaskForm):
    roles = SelectMultipleField('Roles', coerce=int)
    submit = SubmitField('Update Roles')
