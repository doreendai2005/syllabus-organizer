# Syllabus Organizer - Multi-Platform Project

Automatically links academic readings in syllabi to free open-access PDFs.

---

## 🎯 Two Versions Available

### 1. **Python CLI Tool** (Original)
**For**: Technical users who want maximum accuracy and features
**Located**: Root directory (`organizer.py`, `setup_resources.py`)

**Features**:
- 90% classification accuracy (spaCy NLP)
- 8 PDF sources (including Sci-Hub, LibGen, Z-Library)
- PDF downloads & Drive uploads
- Line merging, formatting, organization
- Runs locally

**Quickstart**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 organizer.py
```

See [CLAUDE.md](./CLAUDE.md) for detailed documentation.

---

### 2. **Google Workspace Add-on** (NEW - MVP)
**For**: Non-technical users (professors, students, librarians)
**Located**: `apps-script-addon/` directory

**Features**:
- Zero setup - browser-based
- 70-75% classification accuracy (regex only)
- 5 legal PDF sources only
- One-click operation
- Runs in Google Docs

**Status**: MVP completed, ready for testing
**Deployment**: Manual for now, Marketplace submission planned

See [apps-script-addon/README.md](./apps-script-addon/README.md) for documentation.

---

## 📊 Comparison

| Feature | Python CLI | Google Workspace Add-on |
|---------|-----------|------------------------|
| **Target Users** | Technical | Non-technical |
| **Setup Required** | Python, pip, config files | Just email address |
| **Classification** | 90% (spaCy NLP) | 70-75% (regex) |
| **PDF Sources** | 8 (legal + illegal) | 5 (legal only) |
| **PDF Success** | ~80% | ~40-60% |
| **Deployment** | Local machine | Google Cloud |
| **Cost** | Free | Free (API quotas apply) |

---

## 🚀 Getting Started

### For Technical Users (Python CLI)
1. Clone this repository
2. Follow instructions in [CLAUDE.md](./CLAUDE.md)
3. Run `python3 organizer.py`

### For Non-Technical Users (Add-on)
1. Navigate to `apps-script-addon/`
2. Follow deployment guide in [README.md](./apps-script-addon/README.md)
3. Or wait for Marketplace release (coming soon)

---

## 📁 Project Structure

```
syllabus-organizer/
├── organizer.py              # Python CLI main script
├── setup_resources.py        # Python CLI setup
├── requirements.txt          # Python dependencies
├── config.txt                # Python CLI config
├── CLAUDE.md                 # Python CLI documentation
├── README.md                 # Original README
├── README_PROJECT.md         # This file
│
└── apps-script-addon/        # NEW: Google Workspace Add-on
    ├── Code.gs
    ├── Classifier.gs
    ├── PdfSearch.gs
    ├── DocumentProcessor.gs
    ├── ProgressManager.gs
    ├── Settings.gs
    ├── *.html
    └── README.md
```

---

## 🔮 Future Roadmap

### Short Term (Next 4 weeks)
- [ ] Test add-on with 10 sample syllabi
- [ ] Beta testing with professors/students
- [ ] Bug fixes and performance optimization

### Medium Term (Next 3 months)
- [ ] Google Workspace Marketplace submission
- [ ] Add PDF download/upload to add-on
- [ ] Implement Google NLP API integration (optional)
- [ ] Add basic formatting features

### Long Term (6+ months)
- [ ] Add week-based organization to add-on
- [ ] Batch processing for multiple documents
- [ ] Analytics dashboard
- [ ] Mobile support

---

## ⚖️ Legal Note

**Python CLI**: Includes Sci-Hub, LibGen, Z-Library (may be illegal in some jurisdictions)

**Google Workspace Add-on**: Legal sources only (Unpaywall, Semantic Scholar, CORE, Open Library)

Use responsibly and prefer legal open-access sources when available.

---

## 🤝 Contributing

Contributions welcome for both versions!

- **Python CLI**: Improve NLP accuracy, add more sources, optimize search
- **Add-on**: Better UI/UX, more legal sources, testing

---

## 📄 License

[To be determined - add license here]

---

## 🙏 Credits

- Original Python implementation
- Google Apps Script port
- Open-access sources: Unpaywall, Semantic Scholar, CORE, Internet Archive
