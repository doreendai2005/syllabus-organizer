# Syllabus Automator ✅

Automates linking course readings in a Google Docs syllabus to free online sources (Crossref, Unpaywall, Internet Archive, Anna's Archive, LibGen, Sci-Hub). Use the tool in **dry run** mode first to preview changes.

---

## Quick start ⚡

1. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure Google API credentials:
   - Enable Google Drive & Google Docs APIs in the Google Cloud Console.
   - Create OAuth client credentials (Desktop) and download `credentials.json` to the project root.

4. (Optional) Run the setup script to create a Drive folder and a test Google Doc (this writes `config.txt`):

```bash
python3 setup_resources.py
```

5. Copy `config.example.txt` to `config.txt` (or edit `config.txt`) and set the following keys (one per line):

```
FOLDER_ID=<google_drive_folder_id>
DOC_ID=<google_doc_id>
EMAIL=<your_email_for_unpaywall>
```

6. Run a safe dry-run to preview behavior (no document edits):

```bash
python3 syllabus_automator.py --dry-run
```

7. When ready, run without `--dry-run` to apply links to the document (the script will update the Google Doc):

```bash
python3 syllabus_automator.py
```

Use `--reset` to clear `progress.json` and start fresh:

```bash
python3 syllabus_automator.py --reset
```

---

## What it does 🔧

- Scans the Google Doc for lines that look like reading citations.
- Tries multiple sources (Crossref -> Unpaywall -> Sci-Hub -> Internet Archive -> Anna's Archive -> LibGen) to find a URL or to obtain a PDF.
- If a PDF is downloaded (Sci-Hub path), the script uploads it to the configured Drive folder and links the document text to the Drive file.
- Saves progress to `progress.json` so runs can resume.

> **Note:** In `--dry-run` mode the script will still attempt lookups and downloads to show what *would* happen; it will not modify the Google Doc text. Remove `--dry-run` to apply changes.

---

## Files of interest 📁

- `syllabus_automator.py` — main script
- `setup_resources.py` — create Drive folder and Doc and save to `config.txt`
- `config.example.txt` — example configuration (copy to `config.txt` and edit)
- `google_api.py` — Google auth, docs/drive helper functions
- `sources/` — modules that implement search logic for Crossref, Unpaywall, IA, Anna's Archive, LibGen, Sci-Hub, etc.
- `utils.py` — helper functions and parsers
- `requirements.txt` — Python dependencies
- `tests/` — unit tests (run with `pytest`)

---

## Running tests ✅

Run unit tests locally:

```bash
python3 -m pytest -q
```

All tests for `utils.py` are included and passing.

## Continuous Integration (CI) 🔁

This repository includes a GitHub Actions workflow that runs the test suite on push and pull requests to the `main`/`master` branches. The workflow is defined in `.github/workflows/ci.yml` and tests on Python 3.10 and 3.11.

---

## Configuration & Troubleshooting ⚠️

- Missing `credentials.json` → The script will raise a `FileNotFoundError` and prompt you to download credentials from Google Cloud Console.
- If `config.txt` is missing or `FOLDER_ID`/`DOC_ID` is not set, run `setup_resources.py` or edit `config.txt` manually.
   - Ensure `EMAIL` is set in `config.txt` in the format `EMAIL=you@example.com` (case-insensitive keys are supported). If `EMAIL` is missing Unpaywall lookups will be skipped.
- If `pytest` or other installed script binaries are not available on your `PATH`, ensure your virtualenv is activated or add the pip bin dir to your `PATH`.
- The project was developed for Python 3.10+. You may see warnings with older Python versions.
- Selenium/Sci-Hub: downloads performed by the Sci-Hub selenium path may require a browser and web driver; the script uses `webdriver-manager` to help but check browser/driver compatibility.
   - If PDF downloads fail frequently: check that a supported browser (Chrome/Chromium) is installed, that `webdriver-manager` can download a compatible driver, and consider running with `--dry-run` to inspect the printed Selenium logs. Sci-Hub domains and page layout change frequently; if the script prints a `blob:` or `data:` PDF URL this is a browser-only stream and cannot be downloaded directly by requests.

---

## Legal / Ethical note ⚖️

This project attempts multiple methods to find readings including legal Open Access sources (Crossref & Unpaywall, Internet Archive) and broader sources such as Anna's Archive, LibGen, and Sci-Hub. These latter sources may be illegal in some jurisdictions. Use this tool responsibly and prefer legal open-access copies when available (the script uses Unpaywall first when an email is provided).

---

## Contributing & Extending 💡

- Add more search strategies in `sources/` for other repositories or improve search heuristics in `optimize_search_logic.py`.
- Add more unit and integration tests under `tests/`.

---

If you'd like, I can also add a short example `config.example.txt` or a GitHub Actions CI workflow to run `pytest`. Let me know which you'd prefer next. ✨
