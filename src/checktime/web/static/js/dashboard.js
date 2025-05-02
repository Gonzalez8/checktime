document.addEventListener('DOMContentLoaded', function() {
    // Cargar traducciones necesarias antes de inicializar
    Promise.all([
        loadTranslationGroup('common'),
        loadTranslationGroup('dashboard'),
        loadTranslationGroup('holidays')
    ]).then(() => {
        initializeDashboard();
    }).catch(error => {
        console.error('Error loading translations:', error);
        // Continue initialization even if translations fail
        initializeDashboard();
    });
});

function initializeDashboard() {
    console.log('Initializing dashboard');
    
    // Initialize modals
    const createOverrideModal = new bootstrap.Modal(document.getElementById('createOverrideModal'));
    const editOverrideModal = new bootstrap.Modal(document.getElementById('editOverrideModal'));
    const addHolidayModal = new bootstrap.Modal(document.getElementById('addHolidayModal'));
    const editHolidayModal = new bootstrap.Modal(document.getElementById('editHolidayModal'));
    const selectDayTypeModal = new bootstrap.Modal(document.getElementById('selectDayTypeModal'));
    
    // Get configuration from data attributes
    const calendarDataEl = document.getElementById('calendar-data');
    const currentYear = parseInt(calendarDataEl.getAttribute('data-current-year')) || new Date().getFullYear();
    const currentMonth = parseInt(calendarDataEl.getAttribute('data-current-month')) || new Date().getMonth() + 1;
    const holidayApiUrl = calendarDataEl.getAttribute('data-holiday-api-url') || '/holidays/api/add';
    const calendarPartialUrl = calendarDataEl.getAttribute('data-calendar-partial-url') || '/dashboard/calendar-partial';
    
    console.log('Current year/month:', currentYear, currentMonth);
    
    // Load initial calendar
    loadCalendar(currentYear, currentMonth);
    
    // Initialize Bootstrap tooltips
    initializeTooltips();
    
    // Set up event handlers
    setupEventHandlers(holidayApiUrl, createOverrideModal, editOverrideModal, addHolidayModal, editHolidayModal, selectDayTypeModal);
}

// Helper function to initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[title]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => 
        new bootstrap.Tooltip(tooltipTriggerEl));
}

function setupEventHandlers(holidayApiUrl, createOverrideModal, editOverrideModal, addHolidayModal, editHolidayModal, selectDayTypeModal) {
    // Add single holiday form handler
    const saveHolidayBtn = document.getElementById('saveHoliday');
    if (saveHolidayBtn) {
        saveHolidayBtn.addEventListener('click', function() {
            handleSaveHoliday(holidayApiUrl, addHolidayModal);
        });
    }
    
    // Calendar navigation using event delegation
    document.addEventListener('click', function(e) {
        if (e.target.closest('.calendar-nav')) {
            e.preventDefault();
            const navEl = e.target.closest('.calendar-nav');
            loadCalendar(
                navEl.getAttribute('data-year'), 
                navEl.getAttribute('data-month')
            );
        }
    });
    
    // Calendar cell click handler using event delegation
    document.addEventListener('click', function(e) {
        const cellEl = e.target.closest('.cal-cell');
        if (cellEl) {
            handleCalendarCellClick(cellEl, createOverrideModal, editOverrideModal, addHolidayModal, editHolidayModal, selectDayTypeModal);
        }
    });
    
    // Handle create form submission
    const saveCreateOverrideBtn = document.getElementById('saveCreateOverride');
    if (saveCreateOverrideBtn) {
        saveCreateOverrideBtn.addEventListener('click', function() {
            handleCreateOverride(createOverrideModal);
        });
    }
    
    // Handle edit override form submission
    const saveEditOverrideBtn = document.getElementById('saveEditOverride');
    if (saveEditOverrideBtn) {
        saveEditOverrideBtn.addEventListener('click', function() {
            handleEditOverride(editOverrideModal);
        });
    }
    
    // Handle delete override button click
    const deleteOverrideBtn = document.getElementById('deleteOverrideBtn');
    if (deleteOverrideBtn) {
        deleteOverrideBtn.addEventListener('click', function() {
            handleDeleteOverride(editOverrideModal);
        });
    }
    
    // Handle edit holiday form submission
    const saveEditHolidayBtn = document.getElementById('saveEditHoliday');
    if (saveEditHolidayBtn) {
        saveEditHolidayBtn.addEventListener('click', function() {
            handleEditHoliday(editHolidayModal);
        });
    }
    
    // Handle delete holiday button click
    const deleteHolidayBtn = document.getElementById('deleteHolidayBtn');
    if (deleteHolidayBtn) {
        deleteHolidayBtn.addEventListener('click', function() {
            handleDeleteHoliday(editHolidayModal);
        });
    }
    
    // Handle selection from day type modal
    const createOverrideBtn = document.getElementById('createOverrideBtn');
    if (createOverrideBtn) {
        createOverrideBtn.addEventListener('click', function() {
            const selectedDateEl = document.getElementById('selectedDate');
            const date = selectedDateEl.value;
            selectDayTypeModal.hide();
            
            // Check if this day has schedule data
            const isWorkingDay = selectedDateEl.getAttribute('data-is-working-day') === 'true';
            
            if (isWorkingDay) {
                // Prellenar con datos del schedule
                openCreateOverrideModal(date, createOverrideModal, {
                    check_in_time: selectedDateEl.getAttribute('data-check-in-time'),
                    check_out_time: selectedDateEl.getAttribute('data-check-out-time')
                });
            } else {
                // Sin prellenado
                openCreateOverrideModal(date, createOverrideModal);
            }
        });
    }
    
    const createHolidayBtn = document.getElementById('createHolidayBtn');
    if (createHolidayBtn) {
        createHolidayBtn.addEventListener('click', function() {
            const date = document.getElementById('selectedDate').value;
            selectDayTypeModal.hide();
            openAddHolidayModal(date, addHolidayModal);
        });
    }
}

function handleSaveHoliday(holidayApiUrl, addHolidayModal) {
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
    
    // Use apiRequest helper
    apiRequest(holidayApiUrl, {
        method: 'POST',
        body: data
    }, {
        successMessage: t('holiday_added'),
        errorMessage: t('error_saving_holiday'),
        onSuccess: () => {
            // Close modal and reset form
            addHolidayModal.hide();
            form.reset();
            
            // Reload calendar and upcoming holidays
            reloadCurrentCalendar();
            reloadUpcomingHolidays();
        },
        onError: (data) => {
            if (data.message && data.message.includes('already exists')) {
                document.getElementById('holidayDate').classList.add('is-invalid');
                document.getElementById('holidayDateFeedback').textContent = t('holiday_already_exists');
            }
        }
    });
}

function handleCalendarCellClick(cellEl, createOverrideModal, editOverrideModal, addHolidayModal, editHolidayModal, selectDayTypeModal) {
    console.log('Cell clicked');
    const date = cellEl.getAttribute('data-date');
    console.log('Cell date:', date);
    
    if (!date || date.trim() === '') {
        console.log('No valid date found for this cell');
        return;
    }
    
    // Get the day data from the cell
    const dayData = JSON.parse(cellEl.getAttribute('data-debug') || '{}');
    console.log('Day data:', dayData);
    
    // Check if it's a holiday
    if (dayData.is_holiday) {
        console.log('Clicked on holiday:', dayData.holiday_name);
        openEditHolidayModal(date, dayData.holiday_name, editHolidayModal);
        return;
    }
    
    // Check if there's an existing override
    fetch(`/api/overrides/${date}`)
    .then(response => response.json())
    .then(response => {
        console.log('Override data:', response);
        if (response.success && response.override) {
            // Populate edit form with existing data
            document.getElementById('editOverrideDate').value = date;
            document.getElementById('editCheckInTime').value = response.override.check_in_time || '';
            document.getElementById('editCheckOutTime').value = response.override.check_out_time || '';
            document.getElementById('editDescription').value = response.override.description || '';
            
            // Show edit modal
            editOverrideModal.show();
        } else {
            // Store day data for later use when user chooses override option
            document.getElementById('selectedDate').value = date;
            
            // Store schedule data in data attributes if it's a working day
            if (dayData.is_working_day) {
                document.getElementById('selectedDate').setAttribute('data-is-working-day', 'true');
                document.getElementById('selectedDate').setAttribute('data-check-in-time', dayData.check_in_time || '');
                document.getElementById('selectedDate').setAttribute('data-check-out-time', dayData.check_out_time || '');
                document.getElementById('selectedDate').setAttribute('data-period-name', dayData.period_name || '');
            } else {
                document.getElementById('selectedDate').setAttribute('data-is-working-day', 'false');
            }
            
            // Always show the selection modal
            selectDayTypeModal.show();
        }
    })
    .catch(error => {
        console.error('Error fetching override:', error);
        
        // Default to selection modal
        document.getElementById('selectedDate').value = date;
        selectDayTypeModal.show();
    });
}

function openCreateOverrideModal(date, createOverrideModal, scheduleData = null) {
    // Prepare create form for new override
    document.getElementById('createOverrideDate').value = date;
    
    if (scheduleData) {
        // Prellenar con datos del schedule
        document.getElementById('createCheckInTime').value = scheduleData.check_in_time || '';
        document.getElementById('createCheckOutTime').value = scheduleData.check_out_time || '';
        document.getElementById('createDescription').value = scheduleData.description || '';
    } else {
        // Sin prellenado
        document.getElementById('createCheckInTime').value = '';
        document.getElementById('createCheckOutTime').value = '';
        document.getElementById('createDescription').value = '';
    }
    
    // Show create modal
    createOverrideModal.show();
}

function openAddHolidayModal(date, addHolidayModal) {
    // Format date for input field (YYYY-MM-DD)
    document.getElementById('holidayDate').value = date;
    document.getElementById('holidayDescription').value = '';
    
    // Show the modal
    addHolidayModal.show();
}

function openEditHolidayModal(date, description, editHolidayModal) {
    document.getElementById('editHolidayDate').value = date;
    document.getElementById('editHolidayDescription').value = description || '';
    
    // Show the modal
    editHolidayModal.show();
}

function handleCreateOverride(createOverrideModal) {
    console.log('Create override clicked');
    
    // Reset validation
    resetValidation('createOverrideForm');
    
    const form = document.getElementById('createOverrideForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    
    // Basic validation
    let isValid = true;
    if (!data.date) {
        document.getElementById('createOverrideDate').classList.add('is-invalid');
        isValid = false;
    }
    
    if (!isValid) return;
    
    // Use apiRequest helper
    apiRequest('/api/overrides', {
        method: 'POST',
        body: {
            date: data.date,
            check_in_time: data.check_in_time || null,
            check_out_time: data.check_out_time || null,
            description: data.description || '',
            is_day_off: data.is_day_off === 'on'
        }
    }, {
        successMessage: t('override_created'),
        errorMessage: t('error_creating_override'),
        onSuccess: () => {
            // Close modal
            createOverrideModal.hide();
            form.reset();
            
            // Reload calendar
            reloadCurrentCalendar();
        }
    });
}

function handleEditOverride(editOverrideModal) {
    console.log('Edit override clicked');
    
    // Reset validation
    resetValidation('editOverrideForm');
    
    const form = document.getElementById('editOverrideForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    
    // Basic validation
    let isValid = true;
    if (!data.date) {
        document.getElementById('editOverrideDate').classList.add('is-invalid');
        isValid = false;
    }
    
    if (!isValid) return;
    
    // Use apiRequest helper
    apiRequest(`/api/overrides/${data.date}`, {
        method: 'PUT',
        body: {
            check_in_time: data.check_in_time || null,
            check_out_time: data.check_out_time || null,
            description: data.description || '',
            is_day_off: data.is_day_off === 'on'
        }
    }, {
        successMessage: t('override_updated'),
        errorMessage: t('error_updating_override'),
        onSuccess: () => {
            // Close modal
            editOverrideModal.hide();
            form.reset();
            
            // Reload calendar
            reloadCurrentCalendar();
        }
    });
}

function handleDeleteOverride(editOverrideModal) {
    console.log('Delete override clicked');
    
    const date = document.getElementById('editOverrideDate').value;
    if (!date) {
        showNotification(t('error_missing_date'), 'error');
        return;
    }
    
    // Use apiRequest helper
    apiRequest(`/api/overrides/${date}`, {
        method: 'DELETE'
    }, {
        successMessage: t('override_deleted'),
        errorMessage: t('error_deleting_override'),
        onSuccess: () => {
            // Close modal
            editOverrideModal.hide();
            
            // Reload calendar
            reloadCurrentCalendar();
        }
    });
}

function handleEditHoliday(editHolidayModal) {
    console.log('Save edit holiday clicked');
    
    // Reset validation
    resetValidation('editHolidayForm');
    
    const form = document.getElementById('editHolidayForm');
    const date = document.getElementById('editHolidayDate').value;
    const description = document.getElementById('editHolidayDescription').value;
    
    // Basic validation
    let isValid = true;
    if (!date) {
        document.getElementById('editHolidayDate').classList.add('is-invalid');
        document.getElementById('editHolidayDateFeedback').textContent = t('field_required');
        isValid = false;
    }
    
    if (!description) {
        document.getElementById('editHolidayDescription').classList.add('is-invalid');
        document.getElementById('editHolidayDescriptionFeedback').textContent = t('field_required');
        isValid = false;
    }
    
    if (!isValid) return;
    
    // Use apiRequest helper
    apiRequest('/holidays/api/update', {
        method: 'PUT',
        body: { date, description }
    }, {
        successMessage: t('holiday_updated'),
        errorMessage: t('error_updating_holiday'),
        onSuccess: () => {
            // Close modal
            editHolidayModal.hide();
            form.reset();
            
            // Reload calendar and upcoming holidays
            reloadCurrentCalendar();
            reloadUpcomingHolidays();
        },
        onError: (data) => {
            // Show feedback in form
            const alertEl = document.createElement('div');
            alertEl.className = 'alert alert-danger mt-2';
            alertEl.textContent = data.message || t('error_updating_holiday');
            form.querySelector('.modal-body').appendChild(alertEl);
        }
    });
}

function handleDeleteHoliday(editHolidayModal) {
    console.log('Delete holiday clicked');
    const date = document.getElementById('editHolidayDate').value;
    
    // Use apiRequest helper
    apiRequest(`/holidays/api/delete/${date}`, {
        method: 'DELETE'
    }, {
        successMessage: t('holiday_deleted'),
        errorMessage: t('error_deleting_holiday'),
        onSuccess: () => {
            // Close modal BEFORE reloading to prevent focus issues
            editHolidayModal.hide();
            
            // Reload calendar and upcoming holidays
            reloadCurrentCalendar();
            reloadUpcomingHolidays();
        },
        onError: (data) => {
            // Show feedback in form
            const alertEl = document.createElement('div');
            alertEl.className = 'alert alert-danger mt-2';
            alertEl.textContent = data.message || t('error_deleting_holiday');
            document.getElementById('editHolidayForm').querySelector('.modal-body').appendChild(alertEl);
        }
    });
}

// Helper function to reload current calendar view
function reloadCurrentCalendar() {
    const calendarDataEl = document.getElementById('calendar-data');
    const currentYear = parseInt(calendarDataEl.getAttribute('data-current-year'));
    const currentMonth = parseInt(calendarDataEl.getAttribute('data-current-month'));
    loadCalendar(currentYear, currentMonth);
}

// Helper function to reset validation state
function resetValidation(formId) {
    const invalidInputs = document.querySelectorAll(`#${formId} .is-invalid`);
    invalidInputs.forEach(input => input.classList.remove('is-invalid'));
}

// Function to load calendar content
function loadCalendar(year, month) {
    console.log('Loading calendar:', year, month);
    const calendarDataEl = document.getElementById('calendar-data');
    const calendarPartialUrl = calendarDataEl.getAttribute('data-calendar-partial-url') || '/dashboard/calendar-partial';
    const url = calendarPartialUrl.replace('/0/0', `/${year}/${month}`);
    
    const calendarContainer = document.getElementById('calendar-container');
    calendarContainer.classList.add('loading');
    
    // Use fetch directly here as we're expecting HTML, not JSON
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Calendar load error: ' + response.statusText);
            }
            return response.text();
        })
        .then(html => {
            calendarContainer.innerHTML = html;
            calendarContainer.classList.remove('loading');
            
            // Update data attributes for current view
            calendarDataEl.setAttribute('data-current-year', year);
            calendarDataEl.setAttribute('data-current-month', month);
            
            // Initialize tooltips for the new content
            initializeTooltips();
        })
        .catch(error => {
            console.error('Calendar load error:', error);
            calendarContainer.classList.remove('loading');
            calendarContainer.innerHTML = `<div class='alert alert-danger mt-3'>${t('error_loading_calendar')}</div>`;
            showNotification(t('error_loading_calendar'), 'error');
        });
}

// Function to reload upcoming holidays section
function reloadUpcomingHolidays() {
    console.log('Reloading upcoming holidays');
    const upcomingHolidaysContainer = document.getElementById('upcoming-holidays-container');
    
    if (!upcomingHolidaysContainer) {
        console.error('Upcoming holidays container not found');
        return;
    }
    
    upcomingHolidaysContainer.classList.add('loading');
    
    // Use fetch directly here as we're expecting HTML, not JSON
    fetch('/dashboard/upcoming-holidays-partial')
        .then(response => {
            if (!response.ok) {
                throw new Error('Upcoming holidays load error: ' + response.statusText);
            }
            return response.text();
        })
        .then(html => {
            upcomingHolidaysContainer.innerHTML = html;
            upcomingHolidaysContainer.classList.remove('loading');
            
            // Update statistics section for holiday count
            const statElements = document.querySelectorAll('.card-text.text-muted');
            for (const statElement of statElements) {
                if (statElement.textContent.includes(t('upcoming_holidays'))) {
                    const countElement = statElement.previousElementSibling;
                    if (countElement) {
                        // Count the number of holidays in the updated section
                        const holidayCount = (html.match(/list-group-item/g) || []).length;
                        countElement.textContent = holidayCount;
                    }
                    break;
                }
            }
        })
        .catch(error => {
            console.error('Upcoming holidays load error:', error);
            upcomingHolidaysContainer.classList.remove('loading');
            upcomingHolidaysContainer.innerHTML = `<div class='alert alert-danger mt-3'>${t('error_loading_upcoming_holidays')}</div>`;
            showNotification(t('error_loading_upcoming_holidays'), 'error');
        });
} 