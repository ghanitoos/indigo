document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const progressBar = document.querySelector('#upload-progress .progress-bar');
    const progressContainer = document.getElementById('upload-progress');
    const messageArea = document.getElementById('upload-message');
    const profilePreview = document.getElementById('profile-preview');

    if (dropZone && fileInput) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight(e) {
            dropZone.classList.add('dragover');
        }

        function unhighlight(e) {
            dropZone.classList.remove('dragover');
        }

        dropZone.addEventListener('drop', handleDrop, false);
        fileInput.addEventListener('change', function() {
            handleFiles(this.files);
        });

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }

        function handleFiles(files) {
            if (files.length > 0) {
                const file = files[0];
                uploadFile(file);
            }
        }

        function uploadFile(file) {
            // Validation
            if (file.size > 2 * 1024 * 1024) {
                showMessage(messages.errorSize || 'File too large', 'text-danger');
                return;
            }
            if (!['image/jpeg', 'image/png'].includes(file.type)) {
                showMessage(messages.errorType || 'Invalid file type', 'text-danger');
                return;
            }

            // Preview
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onloadend = function() {
                if (profilePreview.tagName === 'IMG') {
                    profilePreview.src = reader.result;
                } else {
                    // Replace div with img
                    const img = document.createElement('img');
                    img.id = 'profile-preview';
                    img.src = reader.result;
                    img.className = 'profile-avatar-large';
                    img.alt = 'Profile Photo';
                    profilePreview.parentNode.replaceChild(img, profilePreview);
                }
            }

            // Upload
            const formData = new FormData();
            formData.append('file', file);
            
            // X-CSRFToken header is needed for Flask-WTF CSRF protection
            if (csrfToken) {
                formData.append('csrf_token', csrfToken);
            }

            progressContainer.classList.remove('d-none');
            progressBar.style.width = '0%';
            showMessage('', '');

            fetch(uploadUrl, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    progressBar.style.width = '100%';
                    progressBar.classList.add('bg-success');
                    showMessage(data.message, 'text-success');
                    setTimeout(() => {
                        window.location.reload(); 
                    }, 1000);
                } else {
                    progressBar.classList.add('bg-danger');
                    showMessage(data.error, 'text-danger');
                }
            })
            .catch(error => {
                progressBar.classList.add('bg-danger');
                showMessage('Upload failed', 'text-danger');
                console.error('Error:', error);
            });
        }

        function showMessage(msg, className) {
            messageArea.textContent = msg;
            messageArea.className = 'mt-2 small ' + className;
        }
    }
});
