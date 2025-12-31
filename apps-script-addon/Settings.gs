/**
 * Settings Management Module
 * Handles user preferences and configuration
 */

/**
 * Load user settings
 * Uses User Properties to store settings across all documents for this user
 */
function loadSettings() {
  const userProps = PropertiesService.getUserProperties();

  return {
    email: userProps.getProperty('EMAIL') || '',
    coreApiKey: userProps.getProperty('CORE_API_KEY') || '',
    nlpApiKey: userProps.getProperty('NLP_API_KEY') || ''
  };
}

/**
 * Save user settings
 * @param {object} settings - Settings object with email, coreApiKey, nlpApiKey
 */
function saveSettings(settings) {
  const userProps = PropertiesService.getUserProperties();

  if (settings.email) {
    userProps.setProperty('EMAIL', settings.email);
  }

  if (settings.coreApiKey !== undefined) {
    userProps.setProperty('CORE_API_KEY', settings.coreApiKey);
  }

  if (settings.nlpApiKey !== undefined) {
    userProps.setProperty('NLP_API_KEY', settings.nlpApiKey);
  }

  return { success: true };
}

/**
 * Validate settings
 * Returns {valid: boolean, errors: string[]}
 */
function validateSettings(settings) {
  const errors = [];

  // Email is required for Unpaywall
  if (!settings.email || !settings.email.includes('@')) {
    errors.push('Valid email address is required for Unpaywall API');
  }

  return {
    valid: errors.length === 0,
    errors: errors
  };
}

/**
 * Get default settings
 */
function getDefaultSettings() {
  return {
    email: '',
    coreApiKey: '',
    nlpApiKey: ''
  };
}
