document.addEventListener('DOMContentLoaded', function() {
    // Cargar traducciones necesarias antes de inicializar
    Promise.all([
        loadTranslationGroup('common'),
        loadTranslationGroup('schedules')
    ]).then(() => {
        initializeSchedules();
    }).catch(error => {
        console.error('Error loading translations:', error);
        // Continue initialization even if translations fail
        initializeSchedules();
    });

    function initializeSchedules() {
        // Check which page we're on using URL instead of DOM elements
        const path = window.location.pathname;
        
        if (path.includes('/schedules/period/') && path.includes('/days')) {
            // This is the edit_days page
            console.log('Initializing schedule edit days page');
            initializeEditDaysPage();
        } else if (path === '/schedules/add') {
            // This is add schedule period page
            console.log('Initializing add schedule page');
            initializeAddEditPage(false);
        } else if (path.includes('/schedules/edit/')) {
            // This is edit schedule period page
            console.log('Initializing edit schedule page');
            initializeAddEditPage(true);
        } else if (path === '/schedules/' || path === '/schedules') {
            // This is the index page
            console.log('Initializing schedules index page');
            initializeIndexPage();
        }
    }
    
    function initializeEditDaysPage() {
        // Add form submit handler for AJAX submission
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Collect data from form
                const periodId = window.location.pathname.split('/').slice(-2)[0];
                console.log('Period ID:', periodId);
                
                const days = [];
                
                // Process each day
                for (let day = 0; day < 7; day++) {
                    const enabledField = document.getElementById(`day_${day}_enabled`);
                    if (enabledField && enabledField.value === 'on') {
                        const checkInEl = document.getElementById(`day_${day}_check_in`);
                        const checkOutEl = document.getElementById(`day_${day}_check_out`);
                        
                        if (checkInEl && checkOutEl) {
                            const checkIn = checkInEl.value;
                            const checkOut = checkOutEl.value;
                            
                            if (checkIn && checkOut) {
                                days.push({
                                    day_of_week: day,
                                    check_in_time: checkIn,
                                    check_out_time: checkOut
                                });
                            }
                        }
                    }
                }
                
                console.log('Submitting day schedules:', days);
                
                // Send AJAX request using apiRequest
                apiRequest(`/schedules/api/days/update/${periodId}`, {
                    method: 'POST',
                    body: { days: days },
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }, {
                    successMessage: t('day_schedules_updated'),
                    errorMessage: t('error_updating_schedules'),
                    onSuccess: (data) => {
                        console.log('Success response:', data);
                        // After successful update, navigate back to schedules index
                        setTimeout(() => {
                            navigateToSchedulesIndex();
                        }, 1000);
                    },
                    onError: (error) => {
                        console.error('Error response:', error);
                    }
                });
            });
        }
    }
    
    function initializeAddEditPage(isEdit) {
        // Add form submit handler for AJAX submission
        const form = document.querySelector('form');
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Collect data from form
                const formData = new FormData(form);
                const data = Object.fromEntries(formData.entries());
                
                // Convert is_active to boolean
                data.is_active = formData.has('is_active');
                
                // Determine endpoint and method based on operation
                let endpoint, method;
                
                if (isEdit) {
                    const periodId = window.location.pathname.split('/').pop();
                    endpoint = `/schedules/api/update/${periodId}`;
                    method = 'PUT';
                } else {
                    endpoint = '/schedules/api/add';
                    method = 'POST';
                }
                
                console.log('Submitting form data:', data);
                console.log('Endpoint:', endpoint, 'Method:', method);
                
                // Send AJAX request using apiRequest
                apiRequest(endpoint, {
                    method: method,
                    body: data,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }, {
                    successMessage: isEdit ? t('period_updated') : t('period_added'),
                    errorMessage: t('error_saving_period'),
                    onSuccess: (data) => {
                        console.log('Success response:', data);
                        
                        if (isEdit) {
                            // After edit, navigate back to index
                            setTimeout(() => {
                                navigateToSchedulesIndex();
                            }, 1000);
                        } else {
                            // After add, navigate to edit days for the new period
                            if (data.period && data.period.id) {
                                setTimeout(() => {
                                    window.location.href = `/schedules/period/${data.period.id}/days`;
                                }, 1000);
                            } else {
                                // Fallback if no period ID
                                setTimeout(() => {
                                    navigateToSchedulesIndex();
                                }, 1000);
                            }
                        }
                    },
                    onError: (error) => {
                        console.error('Error response:', error);
                    }
                });
            });
        }
    }
    
    function initializeIndexPage() {
        // Add event listeners for delete buttons in modals
        document.querySelectorAll('.modal-footer form').forEach(form => {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                
                // Extract period ID from the form action URL
                const actionUrl = this.getAttribute('action');
                const periodId = actionUrl.split('/').pop();
                
                console.log('Deleting period:', periodId);
                
                // Send AJAX delete request using apiRequest
                apiRequest(`/schedules/api/delete/${periodId}`, {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                }, {
                    successMessage: t('period_deleted'),
                    errorMessage: t('error_deleting_period'),
                    onSuccess: (data) => {
                        console.log('Success response:', data);
                        
                        // Hide the modal
                        const modalId = this.closest('.modal').id;
                        const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
                        if (modal) {
                            modal.hide();
                        }
                        
                        // Reload schedule list instead of full page
                        reloadScheduleList();
                    },
                    onError: (error) => {
                        console.error('Error response:', error);
                    }
                });
            });
        });
    }
});

// Function to toggle day inputs in edit_days.html
function toggleDayInputs(dayIndex) {
    const checkbox = document.getElementById(`day_${dayIndex}_toggle`);
    const inputs = document.getElementById(`day_${dayIndex}_inputs`);
    const enabled = document.getElementById(`day_${dayIndex}_enabled`);
    const checkInInput = document.getElementById(`day_${dayIndex}_check_in`);
    const checkOutInput = document.getElementById(`day_${dayIndex}_check_out`);
    
    inputs.style.display = checkbox.checked ? 'block' : 'none';
    enabled.value = checkbox.checked ? 'on' : '';
    
    // Clear time inputs when disabled
    if (!checkbox.checked) {
        checkInInput.value = '';
        checkOutInput.value = '';
    }
}

// Function to set time value in an input field
function setTime(inputId, timeValue) {
    document.getElementById(inputId).value = timeValue;
}

// Function to apply schedule to a specific day
function applySchedule(dayIndex, checkIn, checkOut) {
    // Toggle on if not already on
    const checkbox = document.getElementById(`day_${dayIndex}_toggle`);
    if (!checkbox.checked) {
        checkbox.checked = true;
        toggleDayInputs(dayIndex);
    }
    
    // Set the time values
    if (checkIn) {
        document.getElementById(`day_${dayIndex}_check_in`).value = checkIn;
    }
    if (checkOut) {
        document.getElementById(`day_${dayIndex}_check_out`).value = checkOut;
    }
}

// Function to apply preset schedules
function applyPreset(presetName) {
    console.log('Applying preset:', presetName);
    
    switch(presetName) {
        case 'standard':
            // Monday to Friday, 9 AM to 6 PM
            for (let day = 0; day < 5; day++) {
                applySchedule(day, '09:00', '18:00');
            }
            // Clear weekend
            const sat = document.getElementById('day_5_toggle');
            const sun = document.getElementById('day_6_toggle');
            if (sat) {
                sat.checked = false;
                toggleDayInputs(5);
            }
            if (sun) {
                sun.checked = false;
                toggleDayInputs(6);
            }
            break;
            
        case 'summer':
            // Summer schedule: Weekdays 8 AM to 3 PM, free weekends
            for (let day = 0; day < 5; day++) {
                applySchedule(day, '08:00', '15:00');
            }
            // Clear weekend
            const satToggle = document.getElementById('day_5_toggle');
            const sunToggle = document.getElementById('day_6_toggle');
            if (satToggle) {
                satToggle.checked = false;
                toggleDayInputs(5);
            }
            if (sunToggle) {
                sunToggle.checked = false;
                toggleDayInputs(6);
            }
            break;
            
        case 'flexible':
            // Flexible schedule: Different hours each day
            applySchedule(0, '09:00', '18:00'); // Monday
            applySchedule(1, '09:00', '18:00'); // Tuesday
            applySchedule(2, '09:00', '18:00'); // Wednesday
            applySchedule(3, '09:00', '18:00'); // Thursday
            applySchedule(4, '08:00', '15:00'); // Friday (short day)
            
            // Clear weekend
            satToggle = document.getElementById('day_5_toggle');
            sunToggle = document.getElementById('day_6_toggle');
            if (satToggle) {
                satToggle.checked = false;
                toggleDayInputs(5);
            }
            if (sunToggle) {
                sunToggle.checked = false;
                toggleDayInputs(6);
            }

            break;
            
        case 'everyday':
            // Every day, 8 AM to 5 PM
            for (let day = 0; day < 7; day++) {
                applySchedule(day, '08:00', '17:00');
            }
            break;
            
        case 'weekday':
            // Monday to Friday, 9 AM to 6 PM
            for (let day = 0; day < 5; day++) {
                applySchedule(day, '09:00', '18:00');
            }
            // Clear weekend
            const weekend1 = document.getElementById('day_5_toggle');
            const weekend2 = document.getElementById('day_6_toggle');
            if (weekend1) {
                weekend1.checked = false;
                toggleDayInputs(5);
            }
            if (weekend2) {
                weekend2.checked = false;
                toggleDayInputs(6);
            }
            break;
            
        case 'weekend':
            // Saturday and Sunday, 10 AM to 2 PM
            // Clear weekdays
            for (let day = 0; day < 5; day++) {
                const toggle = document.getElementById(`day_${day}_toggle`);
                if (toggle) {
                    toggle.checked = false;
                    toggleDayInputs(day);
                }
            }
            applySchedule(5, '10:00', '14:00'); // Saturday
            applySchedule(6, '10:00', '14:00'); // Sunday
            break;
            
        default:
            console.error('Unknown preset:', presetName);
    }
}

// Function to reload the schedule list without reloading the entire page
function reloadScheduleList() {
    console.log('Reloading schedule list');
    const scheduleListContainer = document.querySelector('.schedule-list-container, .card-body');
    
    if (!scheduleListContainer) {
        console.error('Schedule list container not found');
        return;
    }
    
    // Add loading indicator
    scheduleListContainer.classList.add('loading');
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
    loadingOverlay.style.position = 'absolute';
    loadingOverlay.style.top = '0';
    loadingOverlay.style.left = '0';
    loadingOverlay.style.width = '100%';
    loadingOverlay.style.height = '100%';
    loadingOverlay.style.backgroundColor = 'rgba(255, 255, 255, 0.7)';
    loadingOverlay.style.display = 'flex';
    loadingOverlay.style.justifyContent = 'center';
    loadingOverlay.style.alignItems = 'center';
    loadingOverlay.style.zIndex = '1000';
    
    scheduleListContainer.style.position = 'relative';
    scheduleListContainer.appendChild(loadingOverlay);
    
    // Fetch updated schedule list HTML
    fetch('/schedules/partial')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load schedule list');
            }
            return response.text();
        })
        .then(html => {
            // Replace the content with the new HTML
            scheduleListContainer.innerHTML = html;
            scheduleListContainer.classList.remove('loading');
            
            // Reinitialize event listeners and components
            initializeScheduleComponents();
        })
        .catch(error => {
            console.error('Error reloading schedule list:', error);
            scheduleListContainer.removeChild(loadingOverlay);
            scheduleListContainer.classList.remove('loading');
            showNotification(t('error_loading_schedules'), 'error');
        });
}

// Function to navigate to schedules index with partial loading
function navigateToSchedulesIndex() {
    // Check if we're already on the index page
    if (window.location.pathname === '/schedules' || window.location.pathname === '/schedules/') {
        // Just reload the schedule list
        reloadScheduleList();
    } else {
        // Navigate to schedules index
        window.location.href = '/schedules';
    }
}

// Function to initialize components after partial reload
function initializeScheduleComponents() {
    // Re-attach delete form event listeners
    document.querySelectorAll('.modal-footer form').forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const actionUrl = this.getAttribute('action');
            const periodId = actionUrl.split('/').pop();
            
            apiRequest(`/schedules/api/delete/${periodId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }, {
                successMessage: t('period_deleted'),
                errorMessage: t('error_deleting_period'),
                onSuccess: (data) => {
                    // Hide the modal
                    const modalId = this.closest('.modal').id;
                    const modal = bootstrap.Modal.getInstance(document.getElementById(modalId));
                    if (modal) {
                        modal.hide();
                    }
                    
                    // Reload schedule list
                    reloadScheduleList();
                }
            });
        });
    });
    
    // Re-initialize tooltips if needed
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    if (tooltipTriggerList.length > 0) {
        [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    }
    
    // Re-initialize modals if needed
    document.querySelectorAll('[data-bs-toggle="modal"]').forEach(element => {
        element.addEventListener('click', function() {
            const target = this.getAttribute('data-bs-target');
            const modal = new bootstrap.Modal(document.querySelector(target));
            modal.show();
        });
    });
} 