# Syllabus Organizer - Google Workspace Add-on (MVP)

**Automatically link academic readings in Google Docs to free, legal open-access PDFs**

This is a Google Workspace Add-on version of the Syllabus Organizer, designed for non-technical users (professors, students, librarians) who want one-click PDF linking directly in Google Docs.

---

## 🎯 Key Features

- **Zero setup**: One-click install from Google Workspace Marketplace (coming soon)
- **Intelligent citation detection**: 70-75% accuracy using pure regex patterns
- **Legal sources only**: Unpaywall, Semantic Scholar, CORE, Open Library
- **Resumable processing**: Handles long documents with automatic continuation
- **Manual review**: Flags uncertain items for user verification
- **Privacy-focused**: Minimal permissions (current document + Drive uploads only)

---

## 🆚 vs. Python CLI Version

| Feature | Python CLI | Google Workspace Add-on |
|---------|-----------|------------------------|
| **Deployment** | Local installation, requires Python 3.10+ | Browser-based, no installation |
| **User Level** | Technical users | Non-technical users |
| **Setup** | pip install, credentials.json, config.txt | Just email address |
| **PDF Sources** | 8 sources (incl. Sci-Hub, LibGen, Z-Library) | 5 legal sources only |
| **Classification** | 90% accuracy (with spaCy NLP) | 70-75% accuracy (regex only) |
| **PDF Handling** | Downloads & uploads to Drive | Direct hyperlinks (MVP) |
| **Formatting** | Full formatting & organization | Basic linking (MVP) |
| **Line Merging** | Yes (fixes PDF copy-paste) | Not in MVP |

---

## 📁 Project Structure

```
apps-script-addon/
├── appsscript.json          # Manifest, OAuth scopes
├── Code.gs                  # Main entry points, menu
├── Classifier.gs            # Text classification (ported from Python)
├── PdfSearch.gs             # PDF search (5 legal sources)
├── DocumentProcessor.gs     # Document iteration & linking
├── ProgressManager.gs       # Progress tracking & continuation
├── Settings.gs              # User settings management
├── Settings.html            # Settings UI sidebar
├── Progress.html            # Progress UI sidebar
├── Results.html             # Results UI sidebar
└── README.md                # This file
```

---

## 🔧 Technical Architecture

### Classification System (Classifier.gs)

Ported from `organizer.py` lines 401-950 with pure JavaScript regex patterns:

- **`isReading(text)`** - Detects academic citations
  - Strong indicators (+3): Author (Year), et al., quoted titles
  - Medium indicators (+1): Page numbers, publishers, journals, DOIs
  - Negative indicators: Course descriptions, office hours, time ranges
  - Threshold: score >= 3 = reading

- **`isHeader(text)`** - Detects section headers
  - Week/session numbers, dates, course codes
  - 30+ header keywords (readings, assignments, syllabus sections)
  - All-caps short text, text ending with colon

- **`isInstruction(text)`** - Detects assignments/logistics
  - Imperative verbs, due dates, grading info
  - LMS references, office hours, meeting formats
  - Threshold: score >= 3 = instruction

### PDF Search Chain (PdfSearch.gs)

Ported from `organizer.py` lines 984-1274 with only legal sources:

1. **Crossref** → DOI lookup
2. **Unpaywall** → Open access papers (requires email)
3. **Semantic Scholar** → Academic papers (free API)
4. **CORE** → Research papers (optional API key)
5. **Open Library + Internet Archive** → Books & public domain

**Caching**: Uses CacheService (6-hour TTL) to reduce API calls

**Rate Limiting**: Implements delays between requests to respect API limits

### Execution Strategy (ProgressManager.gs + DocumentProcessor.gs)

**Challenge**: Apps Script has 6-minute execution limit

**Solution**: Chunked processing with continuation triggers

```javascript
function processDocument() {
  const MAX_RUNTIME = 5 * 60 * 1000;  // 5-min buffer

  for (let i = progress.currentIndex; i < paragraphs.length; i++) {
    if (elapsed() > MAX_RUNTIME) {
      saveProgress({ currentIndex: i });
      createContinuationTrigger();  // Resume in 1 minute
      return { status: 'PAUSED' };
    }

    processReading(paragraphs[i]);
  }

  return { status: 'COMPLETE' };
}
```

**Progress Persistence**: Uses Document Properties API (tied to specific document)

---

## 🚀 Deployment Guide

### Prerequisites

1. Google account
2. Google Cloud Platform project with Drive & Docs APIs enabled
3. OAuth consent screen configured

### Steps

1. **Create Apps Script Project**:
   ```bash
   # Option 1: Upload via Apps Script IDE
   # Go to script.google.com
   # Create new project
   # Copy all .gs and .html files

   # Option 2: Use clasp CLI
   npm install -g @google/clasp
   clasp login
   clasp create --type docs --title "Syllabus Organizer"
   clasp push
   ```

2. **Configure OAuth Scopes**:
   - Scopes are defined in `appsscript.json`
   - Required: `documents.currentonly`, `drive.file`, `script.external_request`

3. **Test in Development**:
   - Open any Google Doc
   - Refresh → Extensions menu should show "Syllabus Organizer"
   - Configure settings (email address)
   - Process a test syllabus

4. **Deploy as Add-on** (Future):
   - Publish to Google Workspace Marketplace
   - Requires: Privacy policy, terms of service, app review

---

## 📖 User Guide

### First-Time Setup

1. Install add-on from Workspace Marketplace (coming soon)
2. Open a Google Doc with your syllabus
3. Go to **Extensions > Syllabus Organizer > Configure Settings**
4. Enter your email address (required for Unpaywall)
5. (Optional) Enter CORE API key for higher rate limits

### Processing a Syllabus

1. **Extensions > Syllabus Organizer > Process Syllabus**
2. Wait while the add-on:
   - Classifies paragraphs (readings vs headers vs instructions)
   - Searches for PDFs in legal open-access sources
   - Adds hyperlinks to found PDFs
3. Review uncertain items if any
4. Done! Linked readings are now clickable

### Expected Performance

- **Classification accuracy**: 70-75%
- **PDF link success rate**: 40-60% (legal sources only)
- **Processing speed**: ~50 readings per 6 minutes
- **Long documents**: Automatic continuation if > 6 minutes

---

## 🔮 Future Enhancements (Post-MVP)

### Phase 2: Enhanced Features
- **PDF downloads**: Download PDFs to Drive (not just external links)
- **Google NLP API**: Optional integration for 85-90% accuracy
- **Basic formatting**: Bold readings, italicize instructions
- **Week organization**: Create week-based Drive folders

### Phase 3: Advanced Features
- **Line merging**: Fix PDF copy-paste fragmentation
- **Concatenated splitting**: Split "1. Author... 2. Other..." into separate items
- **Advanced formatting**: Week headers, custom fonts
- **Batch processing**: Process multiple documents at once
- **Settings import/export**: Share settings across team

---

## ⚖️ Legal & Ethical

This add-on uses **legal open-access sources only**:

✅ **Legal**:
- Unpaywall (legal OA aggregator)
- Semantic Scholar (Allen Institute, legal)
- CORE (UK repository, legal)
- Open Library / Internet Archive (public domain & legal access)
- Crossref (metadata only)

❌ **Not Included** (in contrast to Python CLI version):
- Sci-Hub (copyright infringement)
- Library Genesis (shadow library)
- Z-Library (illegal, operators indicted)

**Use responsibly**: Prefer legal sources, respect copyright, cite authors properly.

---

## 🐛 Troubleshooting

### "Email not configured" Error
- Go to Settings and enter a valid email address
- Email is required for Unpaywall API access

### Processing Stuck or Slow
- Large documents (200+ readings) may take 20+ minutes
- Add-on automatically pauses and resumes due to 6-min limit
- Check progress in **View Progress** menu

### Low Success Rate (<40%)
- Legal sources have limited coverage compared to illegal alternatives
- Try adding CORE API key in settings for better results
- Some papers may only be available via institutional access

### Classification Errors
- 70-75% accuracy means ~25-30% may be misclassified
- Review uncertain items manually
- Regex-only system has limitations without NLP

---

## 🤝 Contributing

This is an MVP. Contributions welcome!

**Priority areas**:
1. Improve regex patterns for better accuracy
2. Add more legal PDF sources
3. Implement PDF download & upload to Drive
4. Add Google NLP API integration
5. Create comprehensive test suite

---

## 📄 License

Same as parent project (check root LICENSE file)

---

## 🙏 Acknowledgments

- Python CLI version (original implementation)
- Open-access sources: Unpaywall, Semantic Scholar, CORE, Internet Archive
- Google Apps Script platform

---

**Questions?** Open an issue on GitHub or contact the maintainers.
