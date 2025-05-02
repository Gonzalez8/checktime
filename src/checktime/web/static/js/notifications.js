/**
 * CheckTime Notification System
 * 
 * A consistent toast notification system to be used across all modules.
 * This provides visual feedback for user actions without requiring page reloads.
 */

/**
 * Show a notification toast
 * 
 * @param {string} message - The message to display
 * @param {string} type - The type of notification: 'success', 'error', 'warning', 'info'
 * @param {number} duration - How long to show the notification in milliseconds
 */
function showNotification(message, type = 'success', duration = 5000) {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Set the appropriate styles and icons based on type
    let bgColor, textColor, icon;
    switch(type) {
        case 'success':
            bgColor = 'bg-success';
            textColor = 'text-white';
            icon = 'bi-check-circle';
            break;
        case 'error':
            bgColor = 'bg-danger';
            textColor = 'text-white';
            icon = 'bi-exclamation-triangle';
            break;
        case 'warning':
            bgColor = 'bg-warning';
            textColor = 'text-dark';
            icon = 'bi-exclamation-circle';
            break;
        case 'info':
        default:
            bgColor = 'bg-info';
            textColor = 'text-white';
            icon = 'bi-info-circle';
            break;
    }
    
    // Create the toast element with a unique ID
    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header ${bgColor} ${textColor}">
                <strong class="me-auto"><i class="bi ${icon}"></i> ${typeof t === 'function' ? t('notification') : 'Notification'}</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // Add the toast to the container
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show the toast
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: duration
    });
    toast.show();
    
    // Remove toast from DOM after it's hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

/**
 * Handle API responses and show appropriate notifications
 * 
 * @param {Response} response - The fetch API response
 * @param {Object} options - Options for handling the response
 * @param {string} options.successMessage - Message to show on success
 * @param {string} options.errorMessage - Default message to show on error
 * @param {Function} options.onSuccess - Callback to run on success
 * @param {Function} options.onError - Callback to run on error
 * @returns {Promise} - Promise that resolves with the response data
 */
async function handleApiResponse(response, options = {}) {
    const {
        successMessage,
        errorMessage = typeof t === 'function' ? t('error_operation') : 'An error occurred',
        onSuccess,
        onError
    } = options;
    
    try {
        // For 204 No Content responses, we don't need to parse JSON
        if (response.status === 204) {
            if (successMessage) {
                showNotification(successMessage, 'success');
            }
            if (onSuccess) {
                onSuccess({success: true});
            }
            return {success: true};
        }
        
        // Handle HTTP method not allowed errors (405)
        if (response.status === 405) {
            const errorMsg = `405 Method Not Allowed - The requested method is not supported for this endpoint`;
            console.error(errorMsg);
            showNotification(errorMsg, 'error');
            if (onError) {
                onError({success: false, message: errorMsg});
            }
            return {success: false, message: errorMsg};
        }
        
        // Check if response is JSON before trying to parse it
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            // Not a JSON response - show error
            console.error('Non-JSON response received:', response.status, contentType);
            
            // For method not allowed and similar errors
            if (!response.ok) {
                const errorMsg = `${response.status} ${response.statusText}`;
                showNotification(errorMsg, 'error');
                if (onError) {
                    onError({success: false, message: errorMsg});
                }
                return {success: false, message: errorMsg};
            }
            
            // If it's a success response but not JSON, show success message
            if (response.ok && successMessage) {
                showNotification(successMessage, 'success');
                if (onSuccess) {
                    onSuccess({success: true});
                }
                return {success: true};
            }
            
            return {success: response.ok};
        }
        
        // Try to parse JSON safely
        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            console.error('Error parsing JSON:', jsonError);
            const errorMsg = 'Error parsing server response';
            showNotification(errorMsg, 'error');
            if (onError) {
                onError({success: false, message: errorMsg});
            }
            return {success: false, message: errorMsg};
        }
        
        // Process the parsed JSON response
        if (response.ok && (data.success === true || response.status < 300)) {
            if (successMessage) {
                showNotification(successMessage, 'success');
            }
            if (onSuccess) {
                onSuccess(data);
            }
            
            // Handle redirect URLs in response
            if (data.redirect_url) {
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 1000);
            }
            
            return data;
        } else {
            const message = data.message || errorMessage;
            showNotification(message, 'error');
            if (onError) {
                onError(data);
            }
            return data;
        }
    } catch (error) {
        console.error('Error processing API response:', error);
        showNotification(errorMessage, 'error');
        if (onError) {
            onError({success: false, message: error.message});
        }
        return {success: false, message: error.message};
    }
}

/**
 * Perform a standardized fetch API request with proper error handling
 * 
 * @param {string} url - The URL to fetch from
 * @param {Object} options - Fetch options (method, headers, body)
 * @param {Object} responseOptions - Options for handleApiResponse
 * @returns {Promise} - Promise that resolves with the API response data
 */
async function apiRequest(url, options = {}, responseOptions = {}) {
    try {
        // Default headers
        const headers = options.headers || {
            'Content-Type': 'application/json'
        };
        
        // Merge options
        const fetchOptions = {
            method: options.method || 'GET',
            headers,
            ...options
        };
        
        // If the body is an object and not already a string, stringify it
        if (fetchOptions.body && typeof fetchOptions.body === 'object' && !(fetchOptions.body instanceof FormData)) {
            fetchOptions.body = JSON.stringify(fetchOptions.body);
        }
        
        // Try to fetch with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
        
        fetchOptions.signal = controller.signal;
        
        try {
            const response = await fetch(url, fetchOptions);
            clearTimeout(timeoutId);
            return handleApiResponse(response, responseOptions);
        } catch (fetchError) {
            clearTimeout(timeoutId);
            if (fetchError.name === 'AbortError') {
                console.error('Request timed out');
                showNotification('Request timed out. Please try again.', 'error');
                if (responseOptions.onError) {
                    responseOptions.onError({
                        success: false, 
                        message: 'Request timed out'
                    });
                }
                return {success: false, message: 'Request timed out'};
            }
            throw fetchError;
        }
    } catch (error) {
        console.error('API request error:', error);
        showNotification(responseOptions.errorMessage || 'An error occurred while connecting to the server', 'error');
        if (responseOptions.onError) {
            responseOptions.onError({
                success: false, 
                message: error.message
            });
        }
        return {success: false, message: error.message};
    }
} 