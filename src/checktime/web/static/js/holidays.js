document.addEventListener('DOMContentLoaded', function() {
    // Cargar traducciones necesarias antes de inicializar
    Promise.all([
        loadTranslationGroup('common'),
        loadTranslationGroup('holidays')
    ]).then(() => {
        initializeHolidays();
    }).catch(error => {
        console.error('Error loading translations:', error);
        // Continue initialization even if translations fail
        initializeHolidays();
    });

    function initializeHolidays() {
        // Initialize modals
        const addHolidayModal = new bootstrap.Modal(document.getElementById('addHolidayModal'));
        const addRangeModal = new bootstrap.Modal(document.getElementById('addRangeModal'));
        const editHolidayModal = new bootstrap.Modal(document.getElementById('editHolidayModal'));
        
        // Edit holiday button handler
        document.querySelectorAll('.edit-holiday-btn').forEach(button => {
            button.addEventListener('click', function() {
                const id = this.getAttribute('data-id');
                const date = this.getAttribute('data-date');
                const description = this.getAttribute('data-description');
                
                console.log("Editing holiday with ID:", id, "Type:", typeof id);
                
                // Populate edit form
                document.getElementById('editHolidayId').value = id;
                document.getElementById('editHolidayDate').value = date;
                document.getElementById('editHolidayDescription').value = description;
                
                // Show edit modal
                editHolidayModal.show();
            });
        });
        
        // Update holiday form handler
        document.getElementById('updateHoliday').addEventListener('click', function() {
            // Reset validation
            resetValidation('editHolidayForm');
            
            const form = document.getElementById('editHolidayForm');
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            // Convert id to integer
            if (data.id) {
                data.id = parseInt(data.id, 10);
                console.log("Sending ID:", data.id, "Type:", typeof data.id);
            }
            
            // Basic validation
            let isValid = true;
            if (!data.date) {
                document.getElementById('editHolidayDate').classList.add('is-invalid');
                document.getElementById('editHolidayDateFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!data.description) {
                document.getElementById('editHolidayDescription').classList.add('is-invalid');
                document.getElementById('editHolidayDescriptionFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!isValid) return;
            
            // Use the apiRequest helper
            apiRequest('/holidays/api/edit', {
                method: 'POST', 
                body: data
            }, {
                successMessage: t('holiday_updated'),
                errorMessage: t('error_updating_holiday'),
                onSuccess: (data) => {
                    // Close modal and reset form
                    editHolidayModal.hide();
                    form.reset();
                    
                    // Reload holiday list instead of full page
                    reloadHolidayList();
                },
                onError: (data) => {
                    if (data.message && data.message.includes('already exists')) {
                        document.getElementById('editHolidayDate').classList.add('is-invalid');
                        document.getElementById('editHolidayDateFeedback').textContent = t('holiday_already_exists');
                    }
                }
            });
        });
        
        // Delete holiday button handler
        document.querySelectorAll('.delete-holiday-btn').forEach(button => {
            button.addEventListener('click', function() {
                const id = parseInt(this.getAttribute('data-id'), 10);
                const date = this.getAttribute('data-date');
                console.log("Deleting holiday with ID:", id, "Date:", date, "Type:", typeof id);
                
                // Try API endpoint with date if ID fails
                apiRequest('/holidays/api/delete', {
                    method: 'POST',
                    body: { id: id }
                }, {
                    successMessage: t('holiday_deleted'),
                    errorMessage: t('error_deleting_holiday'),
                    onSuccess: (data) => {
                        // Close the delete modal
                        const modal = bootstrap.Modal.getInstance(document.getElementById(`deleteModal${id}`));
                        if (modal) modal.hide();
                        
                        // Reload holiday list instead of full page
                        reloadHolidayList();
                    },
                    onError: (errorData) => {
                        console.error('Error using ID method, trying date method');
                        // If ID method fails, try date method
                        if (date) {
                            apiRequest(`/holidays/api/delete/${date}`, {
                                method: 'DELETE'
                            }, {
                                successMessage: t('holiday_deleted'),
                                errorMessage: t('error_deleting_holiday'),
                                onSuccess: (data) => {
                                    // Close the delete modal
                                    const modal = bootstrap.Modal.getInstance(document.getElementById(`deleteModal${id}`));
                                    if (modal) modal.hide();
                                    
                                    // Reload holiday list instead of full page
                                    reloadHolidayList();
                                }
                            });
                        }
                    }
                });
            });
        });
        
        // Add single holiday form handler
        document.getElementById('saveHoliday').addEventListener('click', function() {
            // Reset validation
            resetValidation('addHolidayForm');
            
            const form = document.getElementById('addHolidayForm');
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            // Basic validation
            let isValid = true;
            if (!data.date) {
                document.getElementById('holidayDate').classList.add('is-invalid');
                document.getElementById('holidayDateFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!data.description) {
                document.getElementById('holidayDescription').classList.add('is-invalid');
                document.getElementById('holidayDescriptionFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!isValid) return;
            
            // Use the apiRequest helper
            apiRequest('/holidays/api/add', {
                method: 'POST',
                body: data
            }, {
                successMessage: t('holiday_added'),
                errorMessage: t('error_saving_holiday'),
                onSuccess: (data) => {
                    // Close modal and reset form
                    addHolidayModal.hide();
                    form.reset();
                    
                    // Reload holiday list instead of full page
                    reloadHolidayList();
                },
                onError: (data) => {
                    if (data.message && data.message.includes('already exists')) {
                        document.getElementById('holidayDate').classList.add('is-invalid');
                        document.getElementById('holidayDateFeedback').textContent = t('holiday_already_exists');
                    }
                }
            });
        });
        
        // Add range form handler
        document.getElementById('saveRange').addEventListener('click', function() {
            // Reset validation
            resetValidation('addRangeForm');
            
            const form = document.getElementById('addRangeForm');
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            // Basic validation
            let isValid = true;
            if (!data.start_date) {
                document.getElementById('rangeStartDate').classList.add('is-invalid');
                document.getElementById('rangeStartDateFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!data.end_date) {
                document.getElementById('rangeEndDate').classList.add('is-invalid');
                document.getElementById('rangeEndDateFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (!data.description) {
                document.getElementById('rangeDescription').classList.add('is-invalid');
                document.getElementById('rangeDescriptionFeedback').textContent = t('field_required');
                isValid = false;
            }
            
            if (data.start_date && data.end_date && new Date(data.start_date) > new Date(data.end_date)) {
                document.getElementById('rangeEndDate').classList.add('is-invalid');
                document.getElementById('rangeEndDateFeedback').textContent = t('end_date_after_start');
                isValid = false;
            }
            
            if (!isValid) return;
            
            // Use the apiRequest helper
            apiRequest('/holidays/api/add-range', {
                method: 'POST',
                body: data
            }, {
                successMessage: t('holidays_added'),
                errorMessage: t('error_saving_holiday'),
                onSuccess: (data) => {
                    // Close modal and reset form
                    addRangeModal.hide();
                    form.reset();
                    
                    // Reload holiday list instead of full page
                    reloadHolidayList();
                }
            });
        });
    }
    
    // Helper functions
    function resetValidation(formId) {
        const invalidInputs = document.querySelectorAll(`#${formId} .is-invalid`);
        invalidInputs.forEach(input => input.classList.remove('is-invalid'));
    }
});

// Function to reload the holiday list without reloading the entire page
function reloadHolidayList() {
    console.log('Reloading holiday list');
    const holidayListContainer = document.querySelector('.holiday-list-container');
    
    if (!holidayListContainer) {
        console.error('Holiday list container not found');
        return;
    }
    
    // Add loading indicator
    holidayListContainer.classList.add('loading');
    holidayListContainer.style.opacity = '0.6';
    
    // Fetch updated holiday list HTML
    fetch('/holidays/partial')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load holiday list');
            }
            return response.text();
        })
        .then(html => {
            // Replace the content with the new HTML
            holidayListContainer.innerHTML = html;
            holidayListContainer.classList.remove('loading');
            holidayListContainer.style.opacity = '1';
            
            // Reinitialize any required UI components
            initializeHolidayComponents();
        })
        .catch(error => {
            console.error('Error reloading holiday list:', error);
            holidayListContainer.classList.remove('loading');
            holidayListContainer.style.opacity = '1';
            showNotification(t('error_loading_holidays'), 'error');
        });
}

// Function to reinitialize components after partial reload
function initializeHolidayComponents() {
    // Re-attach event listeners to buttons
    document.querySelectorAll('.edit-holiday-btn').forEach(button => {
        button.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            const date = this.getAttribute('data-date');
            const description = this.getAttribute('data-description');
            
            // Populate edit form
            document.getElementById('editHolidayId').value = id;
            document.getElementById('editHolidayDate').value = date;
            document.getElementById('editHolidayDescription').value = description;
            
            // Show edit modal
            const editHolidayModal = new bootstrap.Modal(document.getElementById('editHolidayModal'));
            editHolidayModal.show();
        });
    });
    
    document.querySelectorAll('.delete-holiday-btn').forEach(button => {
        button.addEventListener('click', function() {
            const id = parseInt(this.getAttribute('data-id'), 10);
            const date = this.getAttribute('data-date');
            
            // Set up delete modal (if using modals for delete confirmation)
            const deleteModal = document.getElementById(`deleteModal${id}`);
            if (deleteModal) {
                const modal = new bootstrap.Modal(deleteModal);
                modal.show();
            }
        });
    });
    
    // Initialize any third-party components (like datepickers)
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0) {
        [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
} 