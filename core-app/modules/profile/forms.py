from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField
from wtforms.fields import EmailField
from wtforms.validators import DataRequired, Length, Email, Optional

class ProfileForm(FlaskForm):
    display_name = StringField('display_name', validators=[DataRequired(), Length(min=2, max=100)])
    email = EmailField('email', validators=[Optional(), Email()])
    phone = StringField('phone', validators=[Optional(), Length(max=50)])
    department = StringField('department', validators=[Optional(), Length(max=100)])
    bio = TextAreaField('bio', validators=[Optional(), Length(max=500)])
    profile_photo = FileField('profile_photo', validators=[
        FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
    ])
