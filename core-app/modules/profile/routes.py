from flask import render_template, request, flash, redirect, url_for, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from utils.translation import get_text
from utils.file_upload import FileUploadHandler
from . import profile_bp
from .forms import ProfileForm
from models.user import User

@profile_bp.route('/', methods=['GET'])
@login_required
def view_profile():
    return render_template('profile/view.html', user=current_user)

@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(obj=current_user)
    if form.validate_on_submit():
        current_user.update_profile({
            'display_name': form.display_name.data,
            'email': form.email.data,
            'phone': form.phone.data,
            'department': form.department.data,
            'bio': form.bio.data
        })
        flash(get_text('profile.profile_updated'), 'success')
        return redirect(url_for('profile.view_profile'))
    
    return render_template('profile/edit.html', form=form)

@profile_bp.route('/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    if 'file' not in request.files:
        return jsonify({'error': get_text('profile.error_upload')}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': get_text('profile.error_upload')}), 400
        
    valid, error = FileUploadHandler.validate_image(file)
    if not valid:
        return jsonify({'error': error}), 400
        
    # Delete old photo if exists
    if current_user.profile_photo:
        FileUploadHandler.delete_profile_photo(current_user.profile_photo)
        
    filename = FileUploadHandler.save_profile_photo(file, current_user.id)
    if filename:
        current_user.profile_photo = filename
        current_user.update_profile({}) # Trigger updated_at
        return jsonify({
            'success': True, 
            'message': get_text('profile.photo_updated'),
            'url': url_for('profile.get_photo', user_id=current_user.id)
        })
    
    return jsonify({'error': get_text('profile.error_upload')}), 500

@profile_bp.route('/delete-photo', methods=['POST'])
@login_required
def delete_photo():
    if current_user.profile_photo:
        FileUploadHandler.delete_profile_photo(current_user.profile_photo)
        current_user.delete_profile_photo()
        flash(get_text('profile.photo_updated'), 'success') # Reusing photo_updated or add photo_deleted
    return redirect(url_for('profile.edit_profile'))

@profile_bp.route('/photo/<int:user_id>')
@login_required
def get_photo(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.profile_photo:
        return send_from_directory(
            FileUploadHandler.UPLOAD_FOLDER, 
            user.profile_photo
        )
    else:
        # Return 404 or default placeholder if we had one
        return "No photo", 404
