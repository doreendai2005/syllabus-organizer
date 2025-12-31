/**
 * Document Processing Module
 * Processes Google Docs paragraphs and adds PDF links
 */

/**
 * Process the active document
 * Main entry point that coordinates classification and PDF linking
 *
 * Returns: {status: string, statistics: object, uncertainItems: array}
 */
function processDocument() {
  const startTime = new Date().getTime();
  const MAX_RUNTIME = 5 * 60 * 1000;  // 5 minutes buffer (Apps Script has 6-min limit)

  const doc = DocumentApp.getActiveDocument();
  const body = doc.getBody();
  const paragraphs = body.getParagraphs();

  const progress = loadProgress();
  const settings = loadSettings();

  if (!settings.email) {
    throw new Error('Email not configured. Please configure settings first.');
  }

  let processed = 0;

  // Process paragraphs from current index
  for (let i = progress.currentIndex; i < paragraphs.length; i++) {
    // Time check every 10 iterations
    if (i % 10 === 0) {
      const elapsed = new Date().getTime() - startTime;
      if (elapsed > MAX_RUNTIME) {
        progress.currentIndex = i;
        saveProgress(progress);
        createContinuationTrigger();

        return {
          status: 'PAUSED',
          processed: processed,
          remaining: paragraphs.length - i,
          statistics: progress.statistics,
          message: 'Processing paused due to time limit. Will resume automatically in 1 minute.'
        };
      }
    }

    const para = paragraphs[i];
    const text = para.getText().trim();

    if (!text || text.length < 20) {
      progress.processedIndices.push(i);
      continue;
    }

    // Classify paragraph
    const classification = classifyParagraph(text);

    if (classification.type === 'READING') {
      Logger.log(`\nProcessing reading ${progress.statistics.readings + 1}: ${text.substring(0, 60)}...`);

      // Search for PDF
      const pdfUrl = findPdfCached(text, settings.email);

      if (pdfUrl) {
        // Add hyperlink to paragraph
        addLinkToParagraph(para, pdfUrl);
        progress.statistics.linked++;
        Logger.log(`✓ Linked to: ${pdfUrl.substring(0, 80)}`);
      } else {
        progress.statistics.notFound++;
        Logger.log('✗ No PDF found');
      }

      progress.statistics.readings++;
      processed++;

    } else if (classification.type === 'UNCERTAIN') {
      // Flag for manual review
      progress.uncertainItems.push({
        text: text,
        index: i,
        reasons: classification.reasons || [],
        readingScore: classification.readingScore || 0
      });
      Logger.log(`? Uncertain item: ${text.substring(0, 60)}...`);

    } else if (classification.type === 'HEADER') {
      const weekNum = extractWeekNumber(text);
      if (weekNum) {
        progress.currentWeek = weekNum;
        Logger.log(`\n=== Week ${weekNum} ===`);
      }
    }

    progress.processedIndices.push(i);
  }

  // Processing complete
  progress.currentIndex = paragraphs.length;
  progress.status = 'COMPLETE';
  saveProgress(progress);

  // Delete any continuation triggers
  deleteContinuationTriggers();

  return {
    status: 'COMPLETE',
    processed: processed,
    statistics: progress.statistics,
    uncertainItems: progress.uncertainItems
  };
}

/**
 * Add a hyperlink to a paragraph
 * @param {Paragraph} paragraph - The paragraph element to add link to
 * @param {string} url - The URL to link to
 */
function addLinkToParagraph(paragraph, url) {
  try {
    const text = paragraph.editAsText();
    const fullText = text.getText();

    // Link the entire paragraph text
    text.setLinkUrl(0, fullText.length - 1, url);

    // Optional: Change text color to indicate it's linked
    text.setForegroundColor(0, fullText.length - 1, '#1155cc');

  } catch (e) {
    Logger.log(`Error adding link: ${e}`);
  }
}

/**
 * Get document statistics
 * Returns counts of different paragraph types
 */
function getDocumentStats() {
  const doc = DocumentApp.getActiveDocument();
  const body = doc.getBody();
  const paragraphs = body.getParagraphs();

  const stats = {
    total: paragraphs.length,
    readings: 0,
    headers: 0,
    instructions: 0,
    uncertain: 0,
    other: 0
  };

  for (const para of paragraphs) {
    const text = para.getText().trim();
    if (!text || text.length < 20) continue;

    const classification = classifyParagraph(text);
    switch (classification.type) {
      case 'READING':
        stats.readings++;
        break;
      case 'HEADER':
        stats.headers++;
        break;
      case 'INSTRUCTION':
        stats.instructions++;
        break;
      case 'UNCERTAIN':
        stats.uncertain++;
        break;
      default:
        stats.other++;
    }
  }

  return stats;
}

/**
 * Preview classification without processing
 * Useful for testing and debugging
 */
function previewClassification() {
  const doc = DocumentApp.getActiveDocument();
  const body = doc.getBody();
  const paragraphs = body.getParagraphs();

  const results = [];

  for (let i = 0; i < Math.min(paragraphs.length, 50); i++) {  // Preview first 50
    const text = paragraphs[i].getText().trim();
    if (!text || text.length < 20) continue;

    const classification = classifyParagraph(text);
    results.push({
      index: i,
      text: text.substring(0, 100),
      type: classification.type,
      confidence: classification.confidence,
      reasons: classification.reasons || []
    });
  }

  Logger.log(JSON.stringify(results, null, 2));
  return results;
}
