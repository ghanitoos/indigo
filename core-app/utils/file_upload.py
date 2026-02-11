import os
import time
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app

class FileUploadHandler:
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
    UPLOAD_FOLDER = '/opt/admin-panel/data/uploads/profiles'

    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in FileUploadHandler.ALLOWED_EXTENSIONS

    @staticmethod
    def validate_image(file):
        if not file:
            return False, "No file provided"
        
        # Check file extension
        if not FileUploadHandler.allowed_file(file.filename):
            return False, "Invalid file type. Allowed: jpg, jpeg, png"
            
        # Check file size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        
        if file_length > FileUploadHandler.MAX_FILE_SIZE:
            return False, "File is too large (max 2MB)"
            
        return True, None

    @staticmethod
    def generate_filename(user_id):
        timestamp = int(time.time())
        return secure_filename(f"user_{user_id}_{timestamp}.jpg")

    @staticmethod
    def save_profile_photo(file, user_id):
        filename = FileUploadHandler.generate_filename(user_id)
        
        if not os.path.exists(FileUploadHandler.UPLOAD_FOLDER):
            try:
                os.makedirs(FileUploadHandler.UPLOAD_FOLDER, exist_ok=True)
            except OSError as e:
                current_app.logger.error(f"Error creating upload directory: {e}")
                return None

        filepath = os.path.join(FileUploadHandler.UPLOAD_FOLDER, filename)
        
        try:
            image = Image.open(file)
            image = image.convert('RGB')
            # Use getattr for compatibility
            resample = getattr(Image, 'Resampling', Image).LANCZOS
            image = image.resize((300, 300), resample)
            image.save(filepath, "JPEG", quality=85)
            return filename
        except Exception as e:
            current_app.logger.error(f"Error saving profile photo: {e}")
            return None

    @staticmethod
    def delete_profile_photo(filename):
        if not filename:
            return
        
        filepath = os.path.join(FileUploadHandler.UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                current_app.logger.error(f"Error deleting profile photo: {e}")
