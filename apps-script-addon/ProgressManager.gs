/**
 * Progress Management Module
 * Handles progress persistence and continuation triggers for long documents
 */

/**
 * Load progress for current document
 * Uses Document Properties to store progress tied to specific document
 */
function loadProgress() {
  const docProps = PropertiesService.getDocumentProperties();
  const progressJson = docProps.getProperty('PROGRESS');

  if (progressJson) {
    try {
      return JSON.parse(progressJson);
    } catch (e) {
      Logger.log(`Error loading progress: ${e}`);
    }
  }

  // Return default progress object
  return {
    currentIndex: 0,
    currentWeek: 0,
    processedIndices: [],
    status: 'NOT_STARTED',
    statistics: {
      readings: 0,
      linked: 0,
      notFound: 0
    },
    uncertainItems: [],
    startTime: new Date().toISOString()
  };
}

/**
 * Save progress for current document
 */
function saveProgress(progress) {
  const docProps = PropertiesService.getDocumentProperties();
  progress.lastSaved = new Date().toISOString();
  docProps.setProperty('PROGRESS', JSON.stringify(progress));
}

/**
 * Clear all progress for current document
 */
function clearProgress() {
  const docProps = PropertiesService.getDocumentProperties();
  docProps.deleteProperty('PROGRESS');
  Logger.log('Progress cleared');
}

/**
 * Create a time-based trigger to continue processing
 * Trigger will fire after 1 minute to resume processing
 */
function createContinuationTrigger() {
  // Delete any existing continuation triggers first
  deleteContinuationTriggers();

  // Create new trigger to resume after 1 minute
  ScriptApp.newTrigger('processDocument')
    .timeBased()
    .after(60 * 1000)  // 1 minute
    .create();

  Logger.log('Continuation trigger created - will resume in 1 minute');
}

/**
 * Delete all continuation triggers
 */
function deleteContinuationTriggers() {
  const triggers = ScriptApp.getProjectTriggers();

  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'processDocument') {
      ScriptApp.deleteTrigger(trigger);
    }
  }
}

/**
 * Get progress status
 * Returns human-readable progress information
 */
function getProgressStatus() {
  const progress = loadProgress();
  const doc = DocumentApp.getActiveDocument();
  const totalParagraphs = doc.getBody().getParagraphs().length;

  const percentComplete = totalParagraphs > 0
    ? Math.round((progress.currentIndex / totalParagraphs) * 100)
    : 0;

  return {
    status: progress.status,
    percentComplete: percentComplete,
    currentIndex: progress.currentIndex,
    totalParagraphs: totalParagraphs,
    statistics: progress.statistics,
    uncertainCount: progress.uncertainItems.length,
    startTime: progress.startTime,
    lastSaved: progress.lastSaved
  };
}
