/**
 * Syllabus Organizer - Google Workspace Add-on
 * Automatically links academic readings to free, legal open-access PDFs
 *
 * Main entry point and menu integration
 */

/**
 * Creates add-on menu when document is opened
 */
function onOpen(e) {
  DocumentApp.getUi()
    .createAddonMenu()
    .addItem('Process Syllabus', 'showProcessingSidebar')
    .addItem('Configure Settings', 'showSettingsSidebar')
    .addItem('View Progress', 'showProgressSidebar')
    .addSeparator()
    .addItem('Reset Progress', 'resetProgress')
    .addItem('Help & Documentation', 'showHelp')
    .addItem('About', 'showAbout')
    .addToUi();
}

/**
 * Runs when add-on is installed
 */
function onInstall(e) {
  onOpen(e);
}

/**
 * Shows processing sidebar and starts document processing
 */
function showProcessingSidebar() {
  // Check if settings configured
  const settings = loadSettings();
  if (!settings.email) {
    DocumentApp.getUi().alert(
      'Please configure settings first',
      'You need to provide your email address for Unpaywall API access. Click "Configure Settings" from the menu.',
      DocumentApp.getUi().ButtonSet.OK
    );
    showSettingsSidebar();
    return;
  }

  const html = HtmlService.createHtmlOutputFromFile('Progress')
    .setTitle('Processing Syllabus')
    .setWidth(320);
  DocumentApp.getUi().showSidebar(html);
}

/**
 * Shows settings configuration sidebar
 */
function showSettingsSidebar() {
  const template = HtmlService.createTemplateFromFile('Settings');
  template.settings = loadSettings();

  const html = template.evaluate()
    .setTitle('Syllabus Organizer Settings')
    .setWidth(320);
  DocumentApp.getUi().showSidebar(html);
}

/**
 * Shows progress sidebar
 */
function showProgressSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Progress')
    .setTitle('Progress')
    .setWidth(320);
  DocumentApp.getUi().showSidebar(html);
}

/**
 * Resets all progress for current document
 */
function resetProgress() {
  const ui = DocumentApp.getUi();
  const response = ui.alert(
    'Reset Progress',
    'This will clear all progress for this document. Are you sure?',
    ui.ButtonSet.YES_NO
  );

  if (response === ui.Button.YES) {
    clearProgress();
    ui.alert('Progress has been reset.');
  }
}

/**
 * Shows help documentation
 */
function showHelp() {
  const html = HtmlService.createHtmlOutput(`
    <html>
      <head>
        <base target="_blank">
        <style>
          body { font-family: Arial, sans-serif; padding: 15px; }
          h2 { color: #1a73e8; }
          code { background: #f1f3f4; padding: 2px 6px; border-radius: 3px; }
        </style>
      </head>
      <body>
        <h2>Syllabus Organizer Help</h2>

        <h3>How It Works</h3>
        <ol>
          <li>Configure your email in Settings (required for Unpaywall)</li>
          <li>Click "Process Syllabus" to start</li>
          <li>The add-on will:
            <ul>
              <li>Detect academic citations in your document</li>
              <li>Search legal open-access sources for PDFs</li>
              <li>Add hyperlinks to readings</li>
            </ul>
          </li>
          <li>Review uncertain items manually if needed</li>
        </ol>

        <h3>PDF Sources (Legal)</h3>
        <ul>
          <li><strong>Crossref</strong> - DOI lookup</li>
          <li><strong>Unpaywall</strong> - Open access papers</li>
          <li><strong>Semantic Scholar</strong> - Academic papers</li>
          <li><strong>CORE</strong> - Research papers</li>
          <li><strong>Open Library</strong> - Books & public domain</li>
        </ul>

        <h3>Expected Accuracy</h3>
        <ul>
          <li>Citation detection: 70-75%</li>
          <li>PDF link success: 40-60% (legal sources only)</li>
          <li>Processing speed: ~50 readings per 6 minutes</li>
        </ul>

        <h3>Support</h3>
        <p>For issues or questions, visit our <a href="https://github.com/example/syllabus-organizer">GitHub repository</a>.</p>
      </body>
    </html>
  `)
    .setTitle('Help')
    .setWidth(400)
    .setHeight(500);

  DocumentApp.getUi().showModalDialog(html, 'Syllabus Organizer Help');
}

/**
 * Shows about information
 */
function showAbout() {
  const html = HtmlService.createHtmlOutput(`
    <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; padding: 20px; text-align: center; }
          h2 { color: #1a73e8; margin-bottom: 10px; }
          .version { color: #666; font-size: 14px; margin-bottom: 20px; }
          p { line-height: 1.6; }
        </style>
      </head>
      <body>
        <h2>Syllabus Organizer</h2>
        <div class="version">Version 1.0.0 (MVP)</div>

        <p>Automatically links academic readings in your syllabus to free, legal open-access sources.</p>

        <p><strong>Built for:</strong> Professors, students, and librarians</p>

        <p><strong>Legal sources only:</strong><br>
        Unpaywall, Semantic Scholar, CORE, Open Library</p>

        <p style="margin-top: 30px; color: #666; font-size: 12px;">
          Made with ❤️ for accessible education
        </p>
      </body>
    </html>
  `)
    .setWidth(350)
    .setHeight(300);

  DocumentApp.getUi().showModalDialog(html, 'About Syllabus Organizer');
}

/**
 * Include HTML partial files (for CSS, etc.)
 */
function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}
