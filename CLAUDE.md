# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Syllabus Organizer is a Python 3.10+ tool that automatically links academic readings in Google Docs syllabi to free online sources. It processes syllabus documents by merging fragmented text, classifying content using NLP, applying formatting, searching multiple sources for PDFs (Crossref, Unpaywall, Semantic Scholar, CORE, Sci-Hub, LibGen, Open Library, Z-Library, IPFS Library), downloading and uploading to Google Drive, and organizing files by week.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 setup_resources.py          # Create Drive folder and test Doc

# Main script (defaults to --all if no flags specified)
python3 organizer.py                # Run all operations (merge, clean, format, download, organize)
python3 organizer.py --merge        # Step 1: Merge fragmented lines & split numbered lists
python3 organizer.py --clean        # Step 2: Classify content (readings vs non-readings)
python3 organizer.py --format       # Step 3: Apply visual styles based on content type
python3 organizer.py --download     # Step 4: Download PDFs and add links
python3 organizer.py --organize     # Step 5: Organize Drive folder by week
python3 organizer.py --reset        # Clear progress.json and start fresh
python3 organizer.py --debug        # Show detailed debug output

# Testing
python3 -m pytest -q                # Run tests quietly
```

## Architecture

**Core Pipeline (5 sequential steps):**
1. **Merge** (`merge_fragmented_lines_in_doc` + `split_concatenated_lines_in_doc`) - Fixes PDF copy-paste issues by merging incomplete lines and splitting concatenated readings
2. **Clean** (`clean_syllabus`) - Classifies each paragraph as reading/header/instruction/description using NLP + regex
3. **Format** (`format_syllabus`) - Applies visual styles (bold headers, styled readings, etc.)
4. **Download** (`download_readings`) - Searches for PDFs, downloads, uploads to Drive, adds hyperlinks
5. **Organize** (`organize_drive_folder`) - Creates week subfolders and renames files

**NLP-Based Classification (SemanticAnalyzer):**
- Singleton class using spaCy (`en_core_web_md` or `en_core_web_sm`)
- `is_reading()` - Detects academic citations via author patterns, years (1900-2099), page numbers, publishers, and NER (PERSON entities)
- `is_instruction()` - Detects assignments, course logistics using imperative verbs and semantic patterns
- `is_header()` - Detects week headers, dates, section titles
- `is_course_description()` - Detects syllabus metadata (course codes, descriptions, prerequisites)
- Scoring system combines regex patterns + NLP features with weighted confidence

**PDF Search Chain:**

*For Academic Papers (when DOI found):*
1. Crossref (DOI metadata lookup via habanero)
2. Unpaywall (legal open access, requires EMAIL in config.txt)
3. Semantic Scholar (legal open access, searches by DOI or query)
4. CORE (legal open access)
5. Sci-Hub (downloads via requests, falls back if needed)
6. LibGen (mirrors: libgen.is, libgen.rs, libgen.st)

*For Books (no DOI or papers not found):*
1. Open Library / Internet Archive (legal, public domain)
2. LibGen (searches fiction + non-fiction)
3. Z-Library (mirrors: z-lib.gs, z-lib.fm, 1lib.sk)
4. IPFS Library (IPFS-based repository)
5. Semantic Scholar (fallback)
6. CORE (fallback)

**Special Cases:**
- URLs in text → Direct link added to doc (no download)
- Existing PDFs in Drive → Matched via normalized text similarity (no duplicate download)
- No PDF found → Reading left unlinked (no fallback hyperlinks)

**Text Processing Utilities:**
- `merge_fragmented_lines()` - Detects incomplete lines (no period/semicolon, trailing prepositions) and merges with next line
- `split_concatenated_readings()` - Detects numbered lists (e.g., "1. Author (2020)... 2. Other...") and splits into separate paragraphs
- `extract_author_year_pairs()` - Regex-based extraction of citation patterns
- `normalize_text()` - Lowercases, removes punctuation for fuzzy matching

**Key Files:**
- `organizer.py` - Self-contained monolithic script (2900+ lines) with all functionality
- `setup_resources.py` - Creates initial Drive folder and Doc, writes config.txt
- `config.txt` - Configuration (DOC_ID, FOLDER_ID, EMAIL)
- `progress.json` - Tracks processed readings for resumable runs (reading text hash → True)
- `token.json` - Cached OAuth token (auto-generated after first auth)
- `downloads/` - Temporary directory for downloaded PDFs before Drive upload

## Configuration

`config.txt` requires:
```
FOLDER_ID=<google_drive_folder_id>
DOC_ID=<google_doc_id>
EMAIL=<your_email_for_unpaywall>
```

Google OAuth credentials must be in `credentials.json` (downloaded from Google Cloud Console with Drive + Docs API enabled).

## Important Implementation Details

- **spaCy Auto-Download**: First run downloads `en_core_web_sm` model automatically if missing
- **Progress Tracking**: Uses MD5 hash of reading text as key in progress.json to skip already-processed readings
- **API Rate Limiting**: Implements delays (1s) between Semantic Scholar/CORE requests
- **Error Handling**: Most search functions return None on failure and log errors; pipeline continues
- **Drive API**: Uses MediaFileUpload for PDF uploads, batches requests where possible
- **Docs API**: Manipulates Google Docs via `batchUpdate` requests (insert text, apply styles, add hyperlinks)
- **CI/CD**: GitHub Actions runs pytest on Python 3.10 and 3.11 (see .github/workflows/ci.yml)
