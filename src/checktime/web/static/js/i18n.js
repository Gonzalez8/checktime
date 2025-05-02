/**
 * Translation management for JavaScript
 * 
 * This file provides functions to work with translations in JavaScript.
 * It uses the translations provided by the backend through the template.
 */

// Global translations object that will be populated by the template
window.translationsData = window.translationsData || {};

/**
 * Get a translation for a key
 * 
 * @param {string} key - The translation key
 * @param {string} defaultValue - The default value to return if the key is not found
 * @returns {string} - The translated text
 */
function t(key, defaultValue = key) {
    return window.translationsData[key] || defaultValue;
}

/**
 * Load translations from the API for the given keys
 * 
 * @param {Array<string>} keys - Array of translation keys to load
 * @returns {Promise} - Promise that resolves when translations are loaded
 */
function loadTranslations(keys) {
    return fetch(`/api/translations/keys/${keys.join(',')}`)
        .then(response => response.json())
        .then(data => {
            // Merge the new translations with the existing ones
            window.translationsData = {...window.translationsData, ...data};
            return data;
        });
}

/**
 * Load translations for a specific group
 * 
 * @param {string} group - The group name (e.g., 'holidays', 'dashboard', 'common')
 * @returns {Promise} - Promise that resolves when translations are loaded
 */
function loadTranslationGroup(group) {
    return fetch(`/api/translations/group/${group}`)
        .then(response => response.json())
        .then(data => {
            // Merge the new translations with the existing ones
            window.translationsData = {...window.translationsData, ...data};
            console.log(`Loaded ${Object.keys(data).length} translations for group: ${group}`);
            return data;
        })
        .catch(error => {
            console.error(`Error loading translations for group ${group}:`, error);
            return {};
        });
}

/**
 * Add translations to the global translation object
 * 
 * @param {Object} translations - Object with translation keys and values
 */
function addTranslations(translations) {
    window.translationsData = {...window.translationsData, ...translations};
} 