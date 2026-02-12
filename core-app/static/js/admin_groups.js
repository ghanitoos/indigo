$(document).ready(function() {
    // Save Permissions via AJAX
    $('.save-perms-btn').click(function() {
        const btn = $(this);
        const roleId = btn.data('role-id');
        const originalText = btn.html();
        
        // Collect checked modules within the specific card
        const card = btn.closest('.group-card');
        const checkedBoxes = card.find('.module-check:checked');
        const modules = [];
        
        checkedBoxes.each(function() {
            modules.push($(this).val());
        });

        // Show loading state
        btn.prop('disabled', true).html('<i class="fas fa-spinner fa-spin"></i> Saving...');

        // Get CSRF token
        const csrfToken = $('meta[name="csrf-token"]').attr('content');

        $.ajax({
            url: `/admin/group-permissions/update/${roleId}`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ modules: modules }),
            headers: {
                'X-CSRFToken': csrfToken
            },
            success: function(response) {
                if (response.status === 'success') {
                    // toastr is assumed to be available
                    if (typeof toastr !== 'undefined') {
                        toastr.success(response.message);
                    } else {
                        alert(response.message);
                    }
                } else {
                    if (typeof toastr !== 'undefined') {
                        toastr.error(response.message);
                    } else {
                        alert('Error: ' + response.message);
                    }
                }
            },
            error: function(xhr) {
                let msg = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    msg = xhr.responseJSON.message;
                }
                if (typeof toastr !== 'undefined') {
                    toastr.error(msg);
                } else {
                    alert(msg);
                }
            },
            complete: function() {
                btn.prop('disabled', false).html(originalText);
            }
        });
    });

    // Delete Group via AJAX
    $('.delete-group-btn').click(function() {
        if (!confirm('Are you sure you want to delete this group?')) {
            return;
        }

        const btn = $(this);
        const roleId = btn.data('role-id');
        const card = btn.closest('.group-card');
        const csrfToken = $('meta[name="csrf-token"]').attr('content');

        $.ajax({
            url: `/admin/group-permissions/delete/${roleId}`,
            type: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            success: function(response) {
                if (response.status === 'success') {
                    if (typeof toastr !== 'undefined') {
                        toastr.success(response.message);
                    }
                    card.fadeOut(function() {
                        $(this).remove();
                        if ($('.group-card').length === 0) {
                            $('#groups-container').html('<div class="col-md-12"><div class="alert alert-info">No groups added.</div></div>');
                        }
                    });
                } else {
                    if (typeof toastr !== 'undefined') {
                        toastr.error(response.message);
                    }
                }
            },
            error: function(xhr) {
                let msg = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    msg = xhr.responseJSON.message;
                }
                if (typeof toastr !== 'undefined') {
                    toastr.error(msg);
                }
            }
        });
    });
});
