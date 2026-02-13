document.addEventListener('DOMContentLoaded', function() {
    // --- Helper Functions ---
    function notify(type, message) {
        if (typeof toastr !== 'undefined' && toastr[type]) {
            toastr[type](message);
        } else {
            alert((type === 'success' ? 'Meldung: ' : 'Fehler: ') + message);
        }
    }

    // --- Save Permissions Logic ---
    const saveButtons = document.querySelectorAll('.save-perms-btn');
    if (saveButtons.length > 0) {
        console.log('Found ' + saveButtons.length + ' save buttons.');
    }

    saveButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log("Save button clicked");

            const roleId = this.getAttribute('data-role-id');
            const originalText = this.innerHTML;
            const card = this.closest('.group-card');
            
            // Collect checked modules
            const checkedBoxes = card.querySelectorAll('.module-check:checked');
            const modules = Array.from(checkedBoxes).map(cb => cb.value);

            // Show loading state
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Speichern...';

            // Get CSRF token
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;

            if (!csrfToken) {
                alert('Security Error: CSRF Token missing. Please refresh the page.');
                this.disabled = false;
                this.innerHTML = originalText;
                return;
            }

            // Send request
            fetch(`/admin/group-permissions/update/${roleId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ modules: modules })
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.message || 'Server Error'); });
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    notify('success', data.message);
                } else {
                    notify('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                notify('error', error.message || 'Ein Fehler ist aufgetreten.');
            })
            .finally(() => {
                this.disabled = false;
                this.innerHTML = originalText;
            });
        });
    });

    // --- Delete Group Logic ---
    const deleteButtons = document.querySelectorAll('.delete-group-btn');
    
    deleteButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (!confirm('Möchten Sie diese Gruppe wirklich löschen?')) {
                return;
            }

            const roleId = this.getAttribute('data-role-id');
            const card = this.closest('.group-card');
            const csrfMeta = document.querySelector('meta[name="csrf-token"]');
            const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : null;

            fetch(`/admin/group-permissions/delete/${roleId}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    notify('success', data.message);
                    card.style.opacity = '0';
                    setTimeout(() => { card.remove(); }, 500);
                } else {
                    notify('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                notify('error', 'Fehler beim Löschen der Gruppe.');
            });
        });
    });
});
