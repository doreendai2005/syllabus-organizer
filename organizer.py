#!/usr/bin/env python3
"""
Syllabus Organizer - Downloads PDFs, formats syllabus, organizes Drive folder.
Search (Papers): Crossref -> Unpaywall -> Semantic Scholar -> CORE -> Sci-Hub -> LibGen
Search (Books): Open Library -> LibGen -> Z-Library -> IPFS Library
"""

import os
import re
import json
import time
import argparse
import requests
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from bs4 import BeautifulSoup
from habanero import Crossref

# spaCy for semantic analysis
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# Config
SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']
SCIHUB_BASE = "https://sci-hub.se"
IPFS_LIBRARY_BASE = "https://bafyb4icwuj2nkq5qv7rxaoqdqizekozs4crup6ccotifec4jux4hssl3ei.ipfs.dweb.link"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
CORE_API = "https://api.core.ac.uk/v3"
LIBGEN_MIRRORS = ["https://libgen.is", "https://libgen.rs", "https://libgen.st"]
OPEN_LIBRARY_API = "https://openlibrary.org"
ZLIB_MIRRORS = ["https://z-lib.gs", "https://z-lib.fm", "https://1lib.sk"]
DOWNLOADS_DIR = "downloads"
PROGRESS_FILE = "progress.json"
DEBUG_MODE = False  # Set via --debug flag


# =============================================================================
# SEMANTIC ANALYZER - NLP-based text classification using spaCy
# =============================================================================

class SemanticAnalyzer:
    """
    NLP-based text analyzer using spaCy for semantic understanding.
    Detects: authors (PERSON), organizations (ORG), dates, sentence boundaries,
    and distinguishes readings from instructions based on linguistic patterns.
    """

    _instance = None
    _nlp = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if SemanticAnalyzer._nlp is None and SPACY_AVAILABLE:
            self._load_model()

    def _load_model(self):
        """Load spaCy model (downloads if needed)."""
        try:
            # Try to load the medium English model (better NER)
            SemanticAnalyzer._nlp = spacy.load("en_core_web_md")
            print("   ✓ Loaded spaCy model: en_core_web_md")
        except OSError:
            try:
                # Fall back to small model
                SemanticAnalyzer._nlp = spacy.load("en_core_web_sm")
                print("   ✓ Loaded spaCy model: en_core_web_sm")
            except OSError:
                # Download and load small model
                print("   ⏳ Downloading spaCy model (one-time)...")
                import subprocess
                subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"],
                             capture_output=True)
                SemanticAnalyzer._nlp = spacy.load("en_core_web_sm")
                print("   ✓ Downloaded and loaded spaCy model")

    @property
    def nlp(self):
        return SemanticAnalyzer._nlp

    def is_available(self) -> bool:
        """Check if semantic analysis is available."""
        return SPACY_AVAILABLE and self.nlp is not None

    def analyze(self, text: str) -> Dict:
        """
        Perform full semantic analysis on text.
        Returns dict with entities, sentence structure, and classification signals.
        """
        if not self.is_available():
            return {'available': False}

        doc = self.nlp(text)

        # Extract named entities
        persons = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        orgs = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        dates = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
        works = [ent.text for ent in doc.ents if ent.label_ == "WORK_OF_ART"]

        # Sentence analysis
        sentences = list(doc.sents)

        # Check for imperative mood (instructions start with verbs)
        starts_with_verb = False
        if sentences:
            first_sent = sentences[0]
            if len(first_sent) > 0:
                first_token = first_sent[0]
                # Imperative sentences start with base form verb
                starts_with_verb = first_token.pos_ == "VERB" and first_token.tag_ == "VB"

        # Check for academic/publication patterns
        has_publication_pattern = self._has_publication_pattern(doc)

        # Check for instruction patterns (second person, modal verbs)
        has_instruction_pattern = self._has_instruction_pattern(doc)

        return {
            'available': True,
            'persons': persons,
            'organizations': orgs,
            'dates': dates,
            'works_of_art': works,
            'sentence_count': len(sentences),
            'starts_with_verb': starts_with_verb,
            'has_publication_pattern': has_publication_pattern,
            'has_instruction_pattern': has_instruction_pattern,
            'entities_summary': {
                'person_count': len(persons),
                'org_count': len(orgs),
                'date_count': len(dates),
            }
        }

    def _has_publication_pattern(self, doc) -> bool:
        """Check for academic publication patterns."""
        text = doc.text

        # Look for PERSON followed by DATE pattern (Author, Year)
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                # Check if followed by a date within 50 chars
                remaining = text[ent.end_char:ent.end_char + 50]
                if re.search(r'[\(,]\s*\d{4}', remaining):
                    return True

        # Look for publication keywords near ORG entities
        for ent in doc.ents:
            if ent.label_ == "ORG":
                org_lower = ent.text.lower()
                if any(pub in org_lower for pub in ['press', 'publishing', 'journal', 'university']):
                    return True

        return False

    def _has_instruction_pattern(self, doc) -> bool:
        """Check for instruction/assignment patterns."""
        # Look for second person pronouns
        has_you = any(token.text.lower() == "you" for token in doc)

        # Look for modal verbs (should, must, will, can)
        has_modal = any(token.tag_ == "MD" for token in doc)

        # Look for imperative verbs at sentence starts
        imperative_count = 0
        for sent in doc.sents:
            if len(sent) > 0:
                first = sent[0]
                if first.pos_ == "VERB" and first.tag_ == "VB":
                    imperative_count += 1

        return (has_you and has_modal) or imperative_count >= 1

    def get_semantic_score(self, text: str) -> Tuple[int, List[str]]:
        """
        Calculate a semantic-based reading score.
        Returns (score, reasons) - positive scores suggest reading, negative suggest instruction.
        """
        analysis = self.analyze(text)

        if not analysis.get('available'):
            return 0, ["Semantic analysis unavailable"]

        score = 0
        reasons = []

        # PERSON entities suggest author names (+2 each, max +6)
        person_count = analysis['entities_summary']['person_count']
        if person_count > 0:
            bonus = min(person_count * 2, 6)
            score += bonus
            reasons.append(f"+{bonus} Found {person_count} person name(s): {', '.join(analysis['persons'][:3])}")

        # ORG entities that look like publishers (+3)
        for org in analysis['organizations']:
            org_lower = org.lower()
            if any(pub in org_lower for pub in ['press', 'publishing', 'university', 'journal']):
                score += 3
                reasons.append(f"+3 Publisher/academic org: {org}")
                break

        # DATE entities in citation context (+2)
        if analysis['dates']:
            # Check if dates look like publication years
            for date in analysis['dates']:
                if re.match(r'\d{4}$', date.strip()) or re.search(r'\b(19|20)\d{2}\b', date):
                    score += 2
                    reasons.append(f"+2 Publication year detected: {date}")
                    break

        # WORK_OF_ART entities (titles) (+3)
        if analysis['works_of_art']:
            score += 3
            reasons.append(f"+3 Title detected: {analysis['works_of_art'][0][:40]}")

        # Publication pattern detected (+4)
        if analysis['has_publication_pattern']:
            score += 4
            reasons.append("+4 Publication pattern (Author + Year)")

        # Instruction patterns detected (-4)
        if analysis['has_instruction_pattern']:
            score -= 4
            reasons.append("-4 Instruction pattern (you/modal verbs)")

        # Starts with imperative verb (-3)
        if analysis['starts_with_verb']:
            score -= 3
            reasons.append("-3 Starts with imperative verb")

        return score, reasons

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Use spaCy's sentence boundary detection to split text into sentences.
        More accurate than regex-based splitting.
        """
        if not self.is_available():
            # Fallback to simple splitting
            return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    def find_citation_boundaries(self, text: str) -> List[str]:
        """
        Intelligently split text that may contain multiple concatenated citations.
        Uses semantic cues to find where one citation ends and another begins.
        """
        if not self.is_available():
            return [text]

        doc = self.nlp(text)
        citations = []
        current_citation = []

        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue

            # Check if this sentence starts a new citation
            sent_doc = self.nlp(sent_text)
            starts_with_person = False

            # Check if starts with a PERSON entity
            if sent_doc.ents:
                first_ent = sent_doc.ents[0]
                if first_ent.label_ == "PERSON" and first_ent.start_char < 5:
                    starts_with_person = True

            # Also check regex patterns for author names
            if not starts_with_person:
                starts_with_person = bool(re.match(
                    r'^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*[\(,]',
                    sent_text
                ))

            if starts_with_person and current_citation:
                # This looks like a new citation - save current and start new
                citations.append(' '.join(current_citation))
                current_citation = [sent_text]
            else:
                current_citation.append(sent_text)

        if current_citation:
            citations.append(' '.join(current_citation))

        return citations if len(citations) > 1 else [text]

    def is_complete_sentence(self, text: str) -> bool:
        """
        Check if text forms a complete sentence (has subject and verb).
        Useful for detecting sentence fragments from PDF copy-paste.
        """
        if not self.is_available():
            # Fallback: simple heuristic
            return len(text) > 30 and text[0].isupper() and text[-1] in '.!?'

        doc = self.nlp(text)

        # Check for subject and verb
        has_subject = any(token.dep_ in ('nsubj', 'nsubjpass') for token in doc)
        has_verb = any(token.pos_ == 'VERB' for token in doc)

        return has_subject and has_verb

    def classify_text_type(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Classify text as 'reading', 'instruction', 'header', or 'unknown'.
        Returns (classification, confidence, reasons).
        """
        if not self.is_available():
            return 'unknown', 0.0, ["Semantic analysis unavailable"]

        score, reasons = self.get_semantic_score(text)

        # Also check length and basic patterns
        text_len = len(text.strip())

        if text_len < 20:
            return 'unknown', 0.9, ["Too short"]

        # High positive score = reading
        if score >= 6:
            confidence = min(0.95, 0.7 + (score - 6) * 0.05)
            return 'reading', confidence, reasons

        # High negative score = instruction
        if score <= -4:
            confidence = min(0.95, 0.7 + abs(score + 4) * 0.05)
            return 'instruction', confidence, reasons

        # Medium positive = likely reading
        if score >= 3:
            return 'reading', 0.6, reasons

        # Medium negative = likely instruction
        if score <= -2:
            return 'instruction', 0.6, reasons

        # Uncertain
        return 'unknown', 0.3, reasons


# Global semantic analyzer instance
_semantic_analyzer = None

def get_semantic_analyzer() -> SemanticAnalyzer:
    """Get or create the global semantic analyzer."""
    global _semantic_analyzer
    if _semantic_analyzer is None:
        _semantic_analyzer = SemanticAnalyzer()
    return _semantic_analyzer


def load_config() -> dict:
    """Load config from config.txt."""
    config = {}
    if os.path.exists('config.txt'):
        with open('config.txt') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    config[k.strip().upper()] = v.strip().strip("'\"")
    return config


def authenticate():
    """Authenticate with Google."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as f:
            f.write(creds.to_json())
    return creds


def looks_like_author(text: str) -> bool:
    """Check if text starts with what looks like an author name."""
    text = text.strip()
    if not text:
        return False

    # Common author patterns
    author_patterns = [
        # Last name patterns: "Smith", "O'Brien", "van der Berg", "McDonalds"
        r"^[A-Z][a-z]+",                                    # Simple: Smith
        r"^[A-Z]['][A-Z]?[a-z]+",                           # O'Brien, O'Connor
        r"^(?:van|von|de|del|la|le|du|dos|das)\s+[A-Z]",   # van Gogh, de Silva
        r"^Mc[A-Z][a-z]+",                                  # McDonald
        r"^Mac[A-Z][a-z]+",                                 # MacArthur

        # Last, First patterns: "Smith, John" or "Smith, J."
        r"^[A-Z][a-z]+,\s*[A-Z]",

        # Multiple authors: "Smith and Jones", "Smith & Jones"
        r"^[A-Z][a-z]+\s+(?:and|&)\s+[A-Z][a-z]+",

        # Et al: "Smith et al"
        r"^[A-Z][a-z]+\s+et\s+al",
    ]

    for pattern in author_patterns:
        if re.match(pattern, text):
            return True

    return False


def extract_author_year_pairs(text: str) -> list:
    """
    Extract potential author-year citation markers from text.
    Returns list of (start_pos, author, year) tuples.
    """
    pairs = []

    # Pattern: Author (Year) or Author, Year or Author Year
    # Handles: Smith (2020), Smith and Jones (2019), Smith et al. (2018)
    pattern = r'([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?(?:\s+et\s+al\.?)?)\s*[\(,]?\s*(\d{4})\)?'

    for match in re.finditer(pattern, text):
        pairs.append((match.start(), match.group(1), match.group(2)))

    return pairs


def normalize_pdf_text(text: str) -> str:
    """
    Normalize text that was copy-pasted from PDF.
    Fixes common PDF copy-paste issues.
    """
    # Fix common PDF artifacts
    text = text.replace('\u2019', "'")  # Smart quotes
    text = text.replace('\u2018', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    text = text.replace('\u2013', '-')  # En-dash
    text = text.replace('\u2014', '-')  # Em-dash
    text = text.replace('\u00a0', ' ')  # Non-breaking space
    text = text.replace('\ufeff', '')   # BOM

    # Fix hyphenation at line breaks (word- word -> word-word or wordword)
    text = re.sub(r'(\w)-\s+(\w)', r'\1\2', text)

    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def split_concatenated_readings(text: str) -> list:
    """
    Split text that may contain multiple readings concatenated together (PDF copy-paste issue).
    Uses multiple strategies to find split points.
    Returns list of individual reading strings.
    """
    text = normalize_pdf_text(text)
    if not text or len(text) < 40:
        return [text] if text else []

    readings = []

    # Strategy 1: Split on clear author-year boundaries
    # Pattern: end of citation (year) followed by new author
    # e.g., "...(2020). Smith (2019)..." or "...2020. Smith, J. (2019)..."
    split_pattern = r'(\.\s*|\)\s*\.?\s*)([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?(?:\s+et\s+al\.?)?\s*[\(,]\s*\d{4})'

    parts = re.split(split_pattern, text)
    if len(parts) > 1:
        current = ""
        for i, part in enumerate(parts):
            if i % 3 == 0:  # Main text
                current += part
            elif i % 3 == 1:  # Separator (. or ))
                current += part
            else:  # New author-year start
                if current.strip() and len(current.strip()) > 25:
                    readings.append(current.strip())
                current = part
        if current.strip() and len(current.strip()) > 25:
            readings.append(current.strip())

        if len(readings) > 1:
            return readings

    # Strategy 2: Split on bullet points or numbers that precede author names
    # e.g., "1. Smith (2020)... 2. Jones (2019)..."
    bullet_pattern = r'(?:^|[.\s])(\d+[\.\)]\s*|[-•●○]\s*)([A-Z][a-z]+)'
    if re.search(bullet_pattern, text):
        # Split on numbered/bulleted items
        parts = re.split(r'(?:^|\s)(\d+[\.\)]\s*|[-•●○]\s*)(?=[A-Z][a-z]+)', text)
        readings = []
        current = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if re.match(r'^(\d+[\.\)]|[-•●○])$', part):
                if current and len(current) > 25:
                    readings.append(current)
                current = ""
            else:
                current += " " + part if current else part
        if current and len(current) > 25:
            readings.append(current)

        if len(readings) > 1:
            return readings

    # Strategy 3: Split on semicolons followed by author names
    if ';' in text:
        parts = text.split(';')
        readings = []
        for part in parts:
            part = part.strip()
            if part and len(part) > 25:
                # Check if it looks like a reading
                if looks_like_author(part) or re.search(r'\(\d{4}\)', part):
                    readings.append(part)
                elif readings:
                    # Append to previous if it doesn't look like new reading
                    readings[-1] += "; " + part
                else:
                    readings.append(part)

        if len(readings) > 1:
            return readings

    # Strategy 4: Look for multiple author-year patterns and split between them
    pairs = extract_author_year_pairs(text)
    if len(pairs) > 1:
        readings = []
        last_end = 0

        for i, (start, _, _) in enumerate(pairs):
            if i == 0:
                continue

            # Find the best split point (period, semicolon, or significant gap)
            split_point = None

            # Look for period or semicolon followed by space near the author
            for j in range(start - 1, max(last_end, start - 20), -1):
                if text[j] in '.;' and (j + 1 >= len(text) or text[j + 1] == ' '):
                    split_point = j + 1
                    break

            # If no punctuation, check if there's a closing paren followed by space
            if split_point is None:
                for j in range(start - 1, max(last_end, start - 10), -1):
                    if text[j] == ')' and j + 1 < len(text) and text[j + 1] == ' ':
                        split_point = j + 1
                        break

            if split_point and split_point > last_end:
                reading = text[last_end:split_point].strip()
                if reading and len(reading) > 25:
                    readings.append(reading)
                last_end = split_point

        # Add remaining text
        remaining = text[last_end:].strip()
        if remaining and len(remaining) > 25:
            readings.append(remaining)

        if len(readings) > 1:
            return readings

    # No splitting worked, return original
    return [text]


def is_course_description(text: str) -> bool:
    """Check if text is course description, syllabus boilerplate, or administrative info."""
    text_lower = text.lower().strip()

    # Course description patterns
    description_patterns = [
        r'\bthis course\b',
        r'\bthe course\b',
        r'\bthis class\b',
        r'\bthe class\b',
        r'\bthis seminar\b',
        r'\bstudents will\b',
        r'\bstudents learn\b',
        r'\bstudents are\b',
        r'\bwe will\b',
        r'\bwe explore\b',
        r'\bwe examine\b',
        r'\byou will\b',
        r'\byou learn\b',
        r'\bintroduces students\b',
        r'\bdesigned to\b',
        r'\bpurpose of this\b',
        r'\bgoal of this\b',
        r'\baims to\b',
        r'\bseeks to\b',
        r'\bfocuses on\b',
        r'\bexplores\b.*\bthrough\b',
        r'\bexamines\b.*\bthrough\b',
        r'\baddresses\b.*\bquestions?\b',
        r'\bwhat is\b.*\?\s*what\b',  # "What is X? What is Y?"
        r'\bwhat are\b.*\?\s*',
        r'\bhow do\b.*\?',
        r'\bwhy do\b.*\?',
    ]

    for pattern in description_patterns:
        if re.search(pattern, text_lower):
            return True

    return False


def get_instruction_score(text: str, use_semantic: bool = True) -> tuple:
    """
    Calculate a confidence score for whether text is an instruction.
    Combines regex patterns with spaCy semantic analysis for better accuracy.
    Returns (score, reasons) where score >= 3 means likely an instruction.
    """
    text = text.strip()
    score = 0
    reasons = []

    # Remove leading bullets/numbers for analysis
    text_clean = re.sub(r'^[\d\.\)\-•*]+\s*', '', text)
    text_lower = text_clean.lower()

    # === SEMANTIC ANALYSIS (if available) ===
    if use_semantic:
        analyzer = get_semantic_analyzer()
        if analyzer.is_available():
            analysis = analyzer.analyze(text_clean)

            # Instruction pattern detected (+4)
            if analysis.get('has_instruction_pattern'):
                score += 4
                reasons.append("[NLP] +4 Instruction pattern (you/modal verbs)")

            # Starts with imperative verb (+3)
            if analysis.get('starts_with_verb'):
                score += 3
                reasons.append("[NLP] +3 Starts with imperative verb")

            # Publication pattern is a negative indicator for instructions (-3)
            if analysis.get('has_publication_pattern'):
                score -= 3
                reasons.append("[NLP] -3 Has publication pattern (likely reading)")

            # Multiple person names suggest citation, not instruction (-2)
            person_count = analysis.get('entities_summary', {}).get('person_count', 0)
            if person_count >= 2:
                score -= 2
                reasons.append(f"[NLP] -2 Multiple person names ({person_count})")

    # === REGEX PATTERNS (always applied) ===

    # Course description check (+4)
    if is_course_description(text):
        score += 4
        reasons.append("+4 Course description")

    # Strong instruction starters (+3)
    strong_starters = [
        (r'^(read|write|submit|complete|prepare|review|discuss|bring|post|upload|email|send)\s', "Imperative verb start"),
        (r'^(please|note:|note that|you should|you will|you must)\b', "Polite instruction"),
        (r'^(students will|students should|students must)\b', "Student directive"),
        (r'^(be prepared|come prepared|make sure|don\'t forget|remember to)\b', "Preparation instruction"),
        (r'^(assignment|homework|essay|paper due|exam|quiz|midterm|final)\b', "Assignment/exam"),
        (r'^(no class|class canceled|class cancelled)\b', "Class cancellation"),
    ]

    for pattern, reason in strong_starters:
        if re.search(pattern, text_lower):
            score += 3
            reasons.append(f"+3 {reason}")

    # Medium indicators (+2)
    medium_patterns = [
        (r'\boffice\s*hours?\b', "Office hours"),
        (r'\d{1,2}:\d{2}\s*[-–to]+\s*\d{1,2}:\d{2}', "Time range"),
        (r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+\d', "Day + time"),
        (r'\b(due|submit|by|before)\s*(:|on|by)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}/)', "Due date"),
        (r'\b\d+\s*(%|percent|points?)\b', "Grading info"),
        (r'\b(grade|grading|evaluation|attendance|participation)\b', "Assessment term"),
        (r'\b(on canvas|on blackboard|on moodle|on courseworks|course reserve)\b', "LMS reference"),
        (r'\b(in person|in-person|zoom|virtual|hybrid)\b', "Meeting format"),
        (r'\b(film screening|movie:|watch:|view:|listen to)\b', "Media instruction"),
        (r'\b(response paper|reflection|blog post|discussion post|group project|presentation)\b', "Assignment type"),
    ]

    for pattern, reason in medium_patterns:
        if re.search(pattern, text_lower):
            score += 2
            reasons.append(f"+2 {reason}")

    # Weak indicators (+1)
    weak_patterns = [
        (r'\b(tba|tbd|to be announced|to be determined)\b', "TBA/TBD"),
        (r'\b(see |refer to|check |visit )\b', "Reference directive"),
        (r'\b(available on|available at|posted on)\b', "Availability info"),
        (r'\b(professor |prof\.|prof |dr\.|dr |instructor:)\b', "Instructor reference"),
        (r'\b(classroom|room |location:|class time|meeting time)\b', "Location/time info"),
        (r'\b(this week|this class|today we|we will|we are)\b', "Class activity"),
        (r'\b(in class|for class|before class|after class)\b', "Class context"),
    ]

    for pattern, reason in weak_patterns:
        if re.search(pattern, text_lower):
            score += 1
            reasons.append(f"+1 {reason}")

    # Negative indicators (suggest reading, not instruction)
    negative_patterns = [
        (r'^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*[\(,]\s*\d{4}', "Author (Year) format", -3),
        (r'\bpp?\.?\s*\d+[-–]?\d*', "Page numbers", -2),
        (r'\b(journal|quarterly|review|studies|proceedings)\s+of\b', "Academic journal", -2),
        (r'\b(university press|oxford|cambridge|routledge|sage|springer)\b', "Publisher name", -2),
        (r'\b(isbn|doi)\b|doi\.org', "Academic identifier", -2),
    ]

    for pattern, reason, penalty in negative_patterns:
        if re.search(pattern, text_lower):
            score += penalty
            reasons.append(f"{penalty} {reason}")

    return score, reasons


def is_instruction(text: str) -> bool:
    """Check if text is an instruction/assignment rather than a reading. Uses scoring system."""
    text = text.strip()

    # Too short to classify reliably
    if len(text) < 15:
        return False

    # Use semantic-enhanced scoring
    score, _ = get_instruction_score(text)

    # Also check if it's clearly a header (not an instruction)
    if is_header(text):
        return False

    return score >= 3


def is_header(text: str) -> bool:
    """Check if text is a section header (week, topic, etc.)."""
    text_lower = text.lower().strip()
    text_clean = re.sub(r'^[\d\.\)\-•*]+\s*', '', text_lower)  # Remove leading bullets

    # Course title patterns (e.g., "WGST 224: Feminist Approaches" or "SOC 101 - Introduction")
    if re.match(r'^[A-Z]{2,5}\s*\d{2,4}[:\s\-]', text.strip()):
        return True

    # Semester/term in brackets (e.g., "[Spring 2025]" or "(Fall 2024)")
    if re.search(r'\[(spring|fall|summer|winter)\s+\d{4}\]', text_lower):
        return True
    if re.search(r'\((spring|fall|summer|winter)\s+\d{4}\)', text_lower):
        return True

    # Week headers
    if re.match(r'^week\s*\d+', text_clean):
        return True

    # Session/Class/Module headers
    if re.match(r'^(session|class|module|unit|part|section|lecture|seminar|meeting|day)\s*\d+', text_clean):
        return True

    # Date headers (e.g., "October 15" or "10/15" or "Oct 15")
    months = 'january|february|march|april|may|june|july|august|september|october|november|december'
    months_abbr = 'jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec'
    if re.match(rf'^({months}|{months_abbr})\.?\s+\d{{1,2}}', text_clean):
        return True
    if re.match(r'^\d{1,2}/\d{1,2}(/\d{2,4})?$', text_clean):
        return True

    # Day of week headers
    if re.match(r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', text_clean):
        return True

    # Topic/Section headers (short, often in caps or followed by colon)
    header_keywords = [
        'introduction', 'overview', 'conclusion', 'review', 'midterm', 'final',
        'exam', 'break', 'holiday', 'no class', 'thanksgiving', 'spring break',
        'readings', 'required readings', 'recommended readings', 'optional readings',
        'assignments', 'topics', 'schedule', 'theme', 'topic',
        'course policies', 'policies', 'grading', 'grade breakdown',
        'office hours', 'contact', 'instructor', 'professor', 'ta ',
        'teaching assistant', 'course objectives', 'learning objectives',
        'course description', 'description', 'prerequisites', 'materials',
        'required materials', 'textbooks', 'books', 'resources',
    ]
    if any(text_clean == kw or text_clean.startswith(kw + ':') or text_clean.startswith(kw + ' -') for kw in header_keywords):
        return True

    # All caps short text (likely header)
    if len(text) < 60 and text.replace(' ', '').isupper() and len(text) > 3:
        return True

    # Short text ending with colon (likely header)
    if len(text) < 40 and text.endswith(':'):
        return True

    # Roman numeral headers: "I.", "II.", "III." etc.
    if re.match(r'^[IVX]+\.\s', text):
        return True

    return False


def get_reading_score(text: str, use_semantic: bool = True) -> tuple:
    """
    Calculate a confidence score for whether text is a reading.
    Combines regex patterns with spaCy semantic analysis for better accuracy.
    Returns (score, reasons) where score >= 3 means likely a reading.
    """
    text = text.strip()
    score = 0
    reasons = []

    # Remove leading bullets/numbers for analysis
    text_clean = re.sub(r'^[\d\.\)\-•*]+\s*', '', text)

    # === SEMANTIC ANALYSIS (if available) ===
    if use_semantic:
        analyzer = get_semantic_analyzer()
        if analyzer.is_available():
            sem_score, sem_reasons = analyzer.get_semantic_score(text_clean)
            score += sem_score
            reasons.extend([f"[NLP] {r}" for r in sem_reasons])

    # === REGEX PATTERNS (always applied) ===

    # Strong indicators (+3 each)
    strong_patterns = [
        (r'^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*[\(,]\s*\d{4}', "Author (Year)"),
        (r'^[A-Z][a-z]+\s+et\s+al\.?\s*[\(,]?\s*\d{4}', "Author et al. (Year)"),
        (r'^[A-Z][a-z]+,\s*[A-Z][a-z\.]+\s*[\(,]\s*\d{4}', "Last, First (Year)"),
        (r'["\u201c][^"\u201d]{20,}["\u201d]', "Quoted title"),
    ]

    for pattern, reason in strong_patterns:
        if re.search(pattern, text_clean, re.I):
            score += 3
            reasons.append(reason)

    # Medium indicators (+1 each)
    medium_patterns = [
        (r'\(\d{4}\)', "Year in parens"),
        (r',\s*\d{4}[,.\s$]', "Year after comma"),
        (r'pp?\.?\s*\d+[-–]?\d*', "Page numbers"),
        (r'vol\.?\s*\d+', "Volume"),
        (r'no\.?\s*\d+', "Issue number"),
        (r'\bch(?:apter)?\.?\s*\d+', "Chapter"),
        (r'["\'\u201c\u201d].{15,}["\'\u201c\u201d]', "Quoted text"),
        (r'\b[Ee]d(?:s|ited)?\.?\s*(?:by)?\s*[A-Z]', "Editor"),
        (r'\b[Tt]rans(?:lated)?\.?\s*(?:by)?\s*[A-Z]', "Translator"),
        (r'[Uu]niversity\s+[Pp]ress', "University Press"),
        (r'[Jj]ournal\s+of\s+[A-Z]', "Journal of..."),
        (r'\b(?:Quarterly|Review|Studies|Bulletin|Proceedings)\s+(?:of\s+)?[A-Z]', "Academic journal"),
        (r'\b(?:Oxford|Cambridge|Routledge|Sage|Springer|Wiley|Penguin|Harvard|Yale|Princeton)\b', "Major publisher"),
        (r'\b(?:ISBN|DOI)\b|doi\.org|doi:\s*10\.', "Identifier"),
        (r'\(\d+\):\s*\d+[-–]?\d*', "Vol(issue): pages"),
        (r'\bIn:\s+[A-Z][a-z]+', "In: anthology"),
        (r'\bed\.\s+by\s+[A-Z]|\bedited\s+by\s+[A-Z]', "Edited by"),
        (r'excerpts?\s+from|selections?\s+from', "Excerpt/selection"),
    ]

    for pattern, reason in medium_patterns:
        if re.search(pattern, text_clean, re.I):
            score += 1
            reasons.append(reason)

    # Author name bonus (+2) - skip if semantic already detected persons
    if not any('[NLP]' in r and 'person' in r.lower() for r in reasons):
        if looks_like_author(text_clean):
            score += 2
            reasons.append("Starts with author name")

    # Length bonus
    if len(text_clean) > 80:
        score += 1
        reasons.append("Substantial length")

    # Negative indicators
    negative_patterns = [
        (r'^(https?://|www\.)\S+$', "URL only", -2),
        (r'^\d+\s*(%|percent|points?)', "Grading info", -2),
        (r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', "Day of week", -2),
        (r'^\d{1,2}[:/]\d{2}', "Time", -2),
        (r'\bthis course\b', "Course description", -3),
        (r'\bthe course\b', "Course description", -3),
        (r'\bthis class\b', "Course description", -3),
        (r'\bstudents will\b', "Course description", -3),
        (r'\bstudents learn\b', "Course description", -3),
        (r'\bwe will\b', "Course description", -2),
        (r'\boffice hours\b', "Office hours", -3),
        (r'\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}', "Time range", -2),
        (r'\bwhat is\b.*\?', "Question", -2),
        (r'\bhow do\b.*\?', "Question", -2),
        (r'\bin person\b', "Meeting format", -2),
    ]

    for pattern, reason, penalty in negative_patterns:
        if re.search(pattern, text_clean, re.I):
            score += penalty
            reasons.append(f"({penalty}) {reason}")

    return score, reasons


def is_reading(text: str) -> bool:
    """Check if text is a citation/reading. Uses scoring system."""
    text = text.strip()

    # Too short to be a reading
    if len(text) < 20:
        return False

    # Skip if it's a header or instruction
    if is_header(text) or is_instruction(text):
        return False

    score, _ = get_reading_score(text)
    return score >= 3


def clean_query(text: str) -> str:
    """Clean citation for search."""
    text = re.sub(r'pp\.?\s*\d+[-–]?\d*', '', text)
    text = re.sub(r'\(\d{4}\)', '', text)
    text = re.sub(r'vol\.\s*\d+', '', text, flags=re.I)
    return ' '.join(text.split())[:150]


def extract_url(text: str) -> Optional[str]:
    """Extract URL from text if present (for web-based readings)."""
    # Match common URL patterns
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;:!?]'
    match = re.search(url_pattern, text)
    if match:
        return match.group(0)

    # Also check for www. URLs without http
    www_pattern = r'www\.[^\s<>"\')\]]+[^\s<>"\')\].,;:!?]'
    match = re.search(www_pattern, text)
    if match:
        return 'https://' + match.group(0)

    return None


def safe_filename(text: str) -> str:
    """Create safe filename."""
    safe = "".join(c for c in text if c.isalnum() or c in ' -')
    return ' '.join(safe.split())[:50]


def find_doi(text: str) -> Optional[str]:
    """Find DOI via Crossref."""
    try:
        cr = Crossref()
        results = cr.works(query=clean_query(text), limit=1)
        if results['message']['items']:
            doi = results['message']['items'][0].get('DOI')
            if doi:
                print(f"   Found DOI: {doi}")
                return doi
    except Exception as e:
        print(f"   Crossref error: {e}")
    return None


def download_from_scihub(doi: str, filename: str) -> Optional[str]:
    """Download PDF from Sci-Hub."""
    url = f"{SCIHUB_BASE}/{doi}"
    print(f"   Trying Sci-Hub...")

    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Find PDF URL
        pdf_url = None
        for tag in ['embed', 'iframe']:
            elem = soup.find(tag, src=True)
            if elem and '.pdf' in elem.get('src', '').lower():
                pdf_url = elem['src']
                break

        if not pdf_url:
            iframe = soup.find('iframe', id='pdf')
            if iframe:
                pdf_url = iframe.get('src')

        if not pdf_url:
            for a in soup.find_all('a', href=True):
                if '.pdf' in a['href'].lower():
                    pdf_url = a['href']
                    break

        if not pdf_url:
            print("   No PDF found on Sci-Hub")
            return None

        # Fix relative URLs
        if pdf_url.startswith('//'):
            pdf_url = 'https:' + pdf_url
        elif pdf_url.startswith('/'):
            pdf_url = SCIHUB_BASE + pdf_url

        # Download
        print(f"   Downloading PDF...")
        pdf_resp = requests.get(pdf_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)

        if pdf_resp.status_code == 200:
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)
            path = f"{DOWNLOADS_DIR}/{safe_filename(filename)}.pdf"

            with open(path, 'wb') as f:
                f.write(pdf_resp.content)

            # Verify it's a PDF
            with open(path, 'rb') as f:
                if f.read(4) != b'%PDF':
                    os.remove(path)
                    print("   Downloaded file is not a PDF")
                    return None

            size = os.path.getsize(path)
            if size < 1024:
                os.remove(path)
                print("   File too small")
                return None

            print(f"   Saved: {path} ({size:,} bytes)")
            return path

    except Exception as e:
        print(f"   Sci-Hub error: {e}")
    return None


def search_unpaywall(doi: str, email: str) -> Optional[str]:
    """Get open access link via Unpaywall."""
    try:
        url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('is_oa') and data.get('best_oa_location'):
                pdf_url = data['best_oa_location'].get('url_for_pdf')
                if pdf_url:
                    print(f"   Found Unpaywall PDF: {pdf_url[:50]}...")
                    return pdf_url
    except Exception:
        pass
    return None


def search_semantic_scholar(query: str, doi: str = None) -> Optional[str]:
    """Search Semantic Scholar for open access PDF."""
    print(f"   Trying Semantic Scholar...")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}

        # If we have a DOI, search by DOI directly
        if doi:
            url = f"{SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}?fields=openAccessPdf,isOpenAccess"
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('isOpenAccess') and data.get('openAccessPdf'):
                    pdf_url = data['openAccessPdf'].get('url')
                    if pdf_url:
                        print(f"   Found Semantic Scholar PDF!")
                        return pdf_url

        # Fallback to title search
        search_url = f"{SEMANTIC_SCHOLAR_API}/paper/search?query={requests.utils.quote(clean_query(query))}&limit=3&fields=openAccessPdf,isOpenAccess,title"
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for paper in data.get('data', []):
                if paper.get('isOpenAccess') and paper.get('openAccessPdf'):
                    pdf_url = paper['openAccessPdf'].get('url')
                    if pdf_url:
                        print(f"   Found Semantic Scholar PDF!")
                        return pdf_url

    except Exception as e:
        print(f"   Semantic Scholar error: {e}")

    return None


def search_core(query: str, doi: str = None) -> Optional[str]:
    """Search CORE for open access PDF."""
    print(f"   Trying CORE...")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_term = doi if doi else clean_query(query)

        # CORE API search
        url = f"{CORE_API}/search/works?q={requests.utils.quote(search_term)}&limit=5"
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code == 200:
            data = resp.json()
            for result in data.get('results', []):
                # Check for downloadUrl or fullTextLink
                download_url = result.get('downloadUrl')
                if download_url and download_url.endswith('.pdf'):
                    print(f"   Found CORE PDF!")
                    return download_url

                # Check links array
                for link in result.get('links', []):
                    if link.get('type') == 'download' or '.pdf' in link.get('url', ''):
                        print(f"   Found CORE PDF!")
                        return link.get('url')

    except Exception as e:
        print(f"   CORE error: {e}")

    return None


def search_libgen(query: str, doi: str = None) -> Optional[str]:
    """Search Library Genesis for PDF."""
    print(f"   Trying Library Genesis...")

    try:
        search_term = doi if doi else clean_query(query)
        headers = {'User-Agent': 'Mozilla/5.0'}

        for mirror in LIBGEN_MIRRORS:
            try:
                # Search LibGen
                search_url = f"{mirror}/search.php?req={requests.utils.quote(search_term)}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def"
                resp = requests.get(search_url, headers=headers, timeout=15)

                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find result table
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows[1:3]:  # Check first 2 results
                        cells = row.find_all('td')
                        if len(cells) < 9:
                            continue

                        # Get the MD5 hash from the mirrors column (usually last columns have download links)
                        for link in row.find_all('a', href=True):
                            href = link['href']
                            # Look for download links
                            if 'library.lol' in href or 'libgen.lc' in href or '/get/' in href:
                                # Follow to get actual download link
                                try:
                                    dl_resp = requests.get(href, headers=headers, timeout=10)
                                    dl_soup = BeautifulSoup(dl_resp.text, 'html.parser')
                                    for dl_link in dl_soup.find_all('a', href=True):
                                        if 'GET' in dl_link.get_text() or 'download' in dl_link['href'].lower():
                                            pdf_url = dl_link['href']
                                            if pdf_url.startswith('/'):
                                                pdf_url = mirror + pdf_url
                                            print(f"   Found LibGen PDF!")
                                            return pdf_url
                                except:
                                    pass

                            # Direct PDF links
                            if '.pdf' in href.lower():
                                if href.startswith('/'):
                                    href = mirror + href
                                print(f"   Found LibGen PDF!")
                                return href

            except Exception:
                continue

    except Exception as e:
        print(f"   LibGen error: {e}")

    return None


def search_open_library(query: str) -> Optional[str]:
    """Search Open Library for readable/downloadable books."""
    print(f"   Trying Open Library...")

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        search_term = clean_query(query)

        # Search Open Library
        search_url = f"{OPEN_LIBRARY_API}/search.json?q={requests.utils.quote(search_term)}&limit=5"
        resp = requests.get(search_url, headers=headers, timeout=15)

        if resp.status_code != 200:
            return None

        data = resp.json()
        for doc in data.get('docs', []):
            # Check if book has readable version
            if doc.get('has_fulltext') or doc.get('public_scan_b'):
                # Get the edition key
                edition_key = None
                if doc.get('edition_key'):
                    edition_key = doc['edition_key'][0]
                elif doc.get('cover_edition_key'):
                    edition_key = doc['cover_edition_key']

                if edition_key:
                    # Check Read API for downloadable version
                    read_url = f"{OPEN_LIBRARY_API}/api/volumes/brief/olid/{edition_key}.json"
                    read_resp = requests.get(read_url, headers=headers, timeout=10)

                    if read_resp.status_code == 200:
                        read_data = read_resp.json()
                        for record in read_data.get('records', {}).values():
                            # Look for full access items
                            if record.get('data', {}).get('items'):
                                for item in record['data']['items']:
                                    if item.get('status') == 'full access':
                                        # Get Internet Archive PDF link
                                        ia_id = item.get('itemURL', '').split('/')[-1]
                                        if ia_id:
                                            pdf_url = f"https://archive.org/download/{ia_id}/{ia_id}.pdf"
                                            print(f"   Found Open Library PDF!")
                                            return pdf_url

                # Try direct Internet Archive link if available
                if doc.get('ia'):
                    ia_id = doc['ia'][0]
                    pdf_url = f"https://archive.org/download/{ia_id}/{ia_id}.pdf"
                    print(f"   Found Open Library/Archive.org PDF!")
                    return pdf_url

    except Exception as e:
        print(f"   Open Library error: {e}")

    return None


def search_zlibrary(query: str) -> Optional[str]:
    """Search Z-Library for books."""
    print(f"   Trying Z-Library...")

    try:
        search_term = clean_query(query)
        headers = {'User-Agent': 'Mozilla/5.0'}

        for mirror in ZLIB_MIRRORS:
            try:
                # Search Z-Library
                search_url = f"{mirror}/s/{requests.utils.quote(search_term)}?extensions%5B0%5D=pdf"
                resp = requests.get(search_url, headers=headers, timeout=15)

                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                # Find book entries
                for book in soup.find_all(['div', 'article'], class_=lambda x: x and ('book' in x.lower() or 'item' in x.lower() or 'z-book' in str(x).lower())):
                    # Look for download link
                    link = book.find('a', href=True)
                    if link and '/book/' in link['href']:
                        book_url = link['href']
                        if not book_url.startswith('http'):
                            book_url = mirror + book_url

                        # Get book page to find download link
                        try:
                            book_resp = requests.get(book_url, headers=headers, timeout=10)
                            book_soup = BeautifulSoup(book_resp.text, 'html.parser')

                            # Look for download button/link
                            dl_link = book_soup.find('a', href=lambda x: x and '/dl/' in x)
                            if not dl_link:
                                dl_link = book_soup.find('a', class_=lambda x: x and 'download' in str(x).lower())

                            if dl_link and dl_link.get('href'):
                                pdf_url = dl_link['href']
                                if not pdf_url.startswith('http'):
                                    pdf_url = mirror + pdf_url
                                print(f"   Found Z-Library PDF!")
                                return pdf_url
                        except:
                            pass

                # Alternative: Look for direct links in search results
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/dl/' in href or ('/book/' in href and '.pdf' in href.lower()):
                        if not href.startswith('http'):
                            href = mirror + href
                        print(f"   Found Z-Library link!")
                        return href

            except Exception:
                continue

    except Exception as e:
        print(f"   Z-Library error: {e}")

    return None


def search_ipfs_library(query: str, doi: str = None) -> Optional[str]:
    """Search IPFS library for PDF and return download URL."""
    print(f"   Trying IPFS Library...")

    try:
        # Try DOI search first if available
        search_term = doi if doi else clean_query(query)

        # Search the library interface
        search_url = f"{IPFS_LIBRARY_BASE}/#/search/{requests.utils.quote(search_term)}"

        # Fetch the main page to understand the library structure
        resp = requests.get(f"{IPFS_LIBRARY_BASE}/", headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)

        if resp.status_code != 200:
            return None

        # Check if it's a static JSON-based library
        # Try common API patterns for IPFS libraries
        api_endpoints = [
            f"{IPFS_LIBRARY_BASE}/api/search?q={requests.utils.quote(search_term)}",
            f"{IPFS_LIBRARY_BASE}/search.json?q={requests.utils.quote(search_term)}",
            f"{IPFS_LIBRARY_BASE}/books.json",
        ]

        for api_url in api_endpoints:
            try:
                api_resp = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                if api_resp.status_code == 200:
                    try:
                        data = api_resp.json()
                        # Handle different JSON structures
                        if isinstance(data, list):
                            for item in data[:10]:  # Check first 10 results
                                if doi and doi.lower() in str(item).lower():
                                    # Found matching entry, look for download link
                                    for key in ['url', 'download', 'link', 'file', 'ipfs']:
                                        if key in item:
                                            print(f"   Found in IPFS Library!")
                                            return item[key]
                    except json.JSONDecodeError:
                        pass
            except:
                continue

        # Fallback: parse HTML for download links
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Look for search form or links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '.pdf' in href.lower() or '/ipfs/' in href.lower():
                if search_term.split()[0].lower() in link.get_text().lower():
                    if href.startswith('/'):
                        return IPFS_LIBRARY_BASE + href
                    elif href.startswith('ipfs://'):
                        return href.replace('ipfs://', 'https://dweb.link/ipfs/')
                    return href

    except Exception as e:
        print(f"   IPFS Library error: {e}")

    return None


def download_file(url: str, filename: str) -> Optional[str]:
    """Download a file from URL."""
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
        if resp.status_code == 200:
            os.makedirs(DOWNLOADS_DIR, exist_ok=True)
            path = f"{DOWNLOADS_DIR}/{safe_filename(filename)}.pdf"

            with open(path, 'wb') as f:
                f.write(resp.content)

            # Verify PDF
            with open(path, 'rb') as f:
                if f.read(4) != b'%PDF':
                    os.remove(path)
                    return None

            size = os.path.getsize(path)
            if size < 1024:
                os.remove(path)
                return None

            print(f"   Downloaded: {path} ({size:,} bytes)")
            return path
    except Exception as e:
        print(f"   Download error: {e}")
    return None


def upload_to_drive(service, file_path: str, folder_id: str) -> Optional[str]:
    """Upload file to Google Drive."""
    try:
        metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=metadata, media_body=media, fields='webViewLink').execute()
        link = file.get('webViewLink')
        print(f"   Uploaded to Drive!")
        return link
    except Exception as e:
        print(f"   Drive upload error: {e}")
    return None


def list_drive_pdfs(service, folder_id: str) -> List[Dict]:
    """List all PDFs in Drive folder and subfolders."""
    pdfs = []

    def list_folder(fid: str):
        try:
            # Get PDFs in this folder
            query = f"'{fid}' in parents and mimeType='application/pdf' and trashed=false"
            results = service.files().list(q=query, fields='files(id,name,webViewLink)').execute()
            for f in results.get('files', []):
                pdfs.append({
                    'id': f['id'],
                    'name': f['name'],
                    'link': f.get('webViewLink', f"https://drive.google.com/file/d/{f['id']}/view")
                })

            # Check subfolders
            query = f"'{fid}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            folders = service.files().list(q=query, fields='files(id)').execute()
            for folder in folders.get('files', []):
                list_folder(folder['id'])
        except Exception as e:
            print(f"   Error listing Drive folder: {e}")

    list_folder(folder_id)
    return pdfs


def normalize_text(text: str) -> str:
    """Normalize text for matching - lowercase, remove punctuation, extra spaces."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = ' '.join(text.split())
    return text


def match_pdf_to_reading(reading_text: str, pdfs: List[Dict]) -> Optional[Dict]:
    """Try to match a reading to an existing PDF in Drive."""
    reading_norm = normalize_text(reading_text)
    reading_words = set(reading_norm.split())

    # Extract key terms from reading (author names, title words)
    # Remove common words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'for', 'to', 'with', 'by', 'from', 'pp', 'vol', 'chapter', 'ed', 'eds'}
    reading_keywords = reading_words - stop_words

    best_match = None
    best_score = 0

    for pdf in pdfs:
        pdf_name = pdf['name'].replace('.pdf', '').replace('.PDF', '')
        pdf_norm = normalize_text(pdf_name)
        pdf_words = set(pdf_norm.split()) - stop_words

        if not pdf_words:
            continue

        # Calculate overlap score
        common_words = reading_keywords & pdf_words
        if not common_words:
            continue

        # Score based on percentage of PDF name words found in reading
        score = len(common_words) / len(pdf_words)

        # Bonus for author name match (usually first word of PDF name)
        pdf_first_word = pdf_norm.split()[0] if pdf_norm.split() else ''
        if pdf_first_word and len(pdf_first_word) > 2 and pdf_first_word in reading_norm:
            score += 0.3

        if score > best_score and score >= 0.4:  # Minimum 40% match threshold
            best_score = score
            best_match = pdf

    return best_match


def add_link_to_doc(service, doc_id: str, start: int, end: int, url: str):
    """Add hyperlink to document."""
    service.documents().batchUpdate(
        documentId=doc_id,
        body={'requests': [{
            'updateTextStyle': {
                'range': {'startIndex': start, 'endIndex': end},
                'textStyle': {'link': {'url': url}},
                'fields': 'link'
            }
        }]}
    ).execute()


def get_doc_content(service, doc_id: str) -> list:
    """Get document text lines with indices."""
    doc = service.documents().get(documentId=doc_id).execute()
    lines = []

    def read(elements):
        for el in elements:
            if 'paragraph' in el:
                for pe in el['paragraph'].get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '').strip()
                        if text:
                            lines.append({
                                'text': text,
                                'start': pe.get('startIndex'),
                                'end': pe.get('endIndex')
                            })
            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        read(cell.get('content', []))

    read(doc.get('body', {}).get('content', []))
    return lines


def load_progress(doc_id: str) -> set:
    """Load processed indices."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
                if data.get('doc_id') == doc_id:
                    return set(data.get('done', []))
        except:
            pass
    return set()


def save_progress(doc_id: str, done: set):
    """Save progress."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'doc_id': doc_id, 'done': list(done), 'updated': datetime.now().isoformat()}, f)


def find_pdf(text: str, email: str = None) -> Optional[str]:
    """
    Find and download PDF for a reading.
    Search chain:
      Papers: Crossref -> Unpaywall -> Semantic Scholar -> CORE -> Sci-Hub
      Books: Open Library -> LibGen -> Z-Library -> IPFS Library
    Returns local_path or None. No fallback links - if not found, returns None.
    """
    filename = text[:50]

    # Step 1: Find DOI via Crossref (indicates academic paper)
    doi = find_doi(text)

    if doi:
        # Academic paper sources
        # Step 2: Try Unpaywall (legal OA)
        if email:
            pdf_url = search_unpaywall(doi, email)
            if pdf_url:
                local = download_file(pdf_url, filename)
                if local:
                    return local

        # Step 3: Try Semantic Scholar (legal OA)
        pdf_url = search_semantic_scholar(text, doi)
        if pdf_url:
            local = download_file(pdf_url, filename)
            if local:
                return local

        # Step 4: Try CORE (legal OA)
        pdf_url = search_core(text, doi)
        if pdf_url:
            local = download_file(pdf_url, filename)
            if local:
                return local

        # Step 5: Try Sci-Hub (papers)
        local = download_from_scihub(doi, filename)
        if local:
            return local

        # Step 6: Try Library Genesis (papers section)
        pdf_url = search_libgen(text, doi)
        if pdf_url:
            local = download_file(pdf_url, filename)
            if local:
                return local

    # Book and general sources (no DOI or DOI sources failed)
    # Try Open Library (legal, public domain books)
    pdf_url = search_open_library(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # Try Library Genesis (books)
    pdf_url = search_libgen(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # Try Z-Library (books)
    pdf_url = search_zlibrary(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # Try IPFS Library
    pdf_url = search_ipfs_library(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # Try Semantic Scholar without DOI
    pdf_url = search_semantic_scholar(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # Try CORE without DOI
    pdf_url = search_core(text)
    if pdf_url:
        local = download_file(pdf_url, filename)
        if local:
            return local

    # No PDF found - return None (no fallback hyperlink)
    return None


def is_week_header(text: str) -> Optional[int]:
    """Check if text is a week header, return week number or None."""
    match = re.match(r'^\s*week\s+(\d+)', text, re.I)
    if match:
        return int(match.group(1))
    return None


def extract_author_title(text: str) -> str:
    """Extract author and title from citation for filename."""
    # Try to find author (usually first part before year or comma)
    author = ""
    title = ""

    # Look for pattern: Author (Year) or Author, Year
    author_match = re.match(r'^([A-Za-z\-\']+(?:\s+(?:and|&)\s+[A-Za-z\-\']+)?(?:\s+et\s+al\.?)?)', text)
    if author_match:
        author = author_match.group(1).strip()

    # Look for quoted title
    title_match = re.search(r'["\u201c]([^"\u201d]+)["\u201d]', text)
    if title_match:
        title = title_match.group(1).strip()[:50]
    else:
        # Use part after author as title
        remaining = text[len(author):] if author else text
        remaining = re.sub(r'\(\d{4}\)', '', remaining)
        remaining = re.sub(r'pp\.?\s*\d+[-–]?\d*', '', remaining)
        title = ' '.join(remaining.split())[:50]

    if author and title:
        return f"{author} - {title}"
    elif author:
        return author
    elif title:
        return title
    return safe_filename(text[:50])


def get_or_create_folder(drive_service, parent_id: str, folder_name: str) -> str:
    """Get existing folder or create new one, return folder ID."""
    # Search for existing folder
    query = f"'{parent_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = drive_service.files().list(q=query, fields='files(id)').execute()
    files = results.get('files', [])

    if files:
        return files[0]['id']

    # Create new folder
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = drive_service.files().create(body=metadata, fields='id').execute()
    print(f"   Created folder: {folder_name}")
    return folder['id']


def is_incomplete_line(text: str) -> bool:
    """Check if a line looks like it was cut off mid-reading (PDF line break issue)."""
    text = text.strip()
    if not text:
        return False

    # Use spaCy to check if it's a complete sentence
    analyzer = get_semantic_analyzer()
    if analyzer.is_available():
        # If spaCy says it's not a complete sentence, it's likely incomplete
        if not analyzer.is_complete_sentence(text):
            # But only if it has some reading-like characteristics
            if looks_like_author(text) or re.search(r'\(\d{4}\)', text) or len(text) > 30:
                return True

    # Ends with word that suggests continuation
    incomplete_endings = [
        ' in', ' in:', ' the', ' a', ' an', ' and', ' or', ' of', ' for', ' to',
        ' by', ' from', ' with', ' on', ' at', ' as', ',', ':', ';',
        ' vol', ' vol.', ' pp', ' pp.', ' ed', ' ed.', ' eds', ' eds.',
        ' trans', ' trans.', ' chapter', ' ch', ' ch.', '&',
        ' new', ' york', ' cambridge', ' oxford', ' london', ' chicago',
    ]
    text_lower = text.lower()
    if any(text_lower.endswith(e) for e in incomplete_endings):
        return True

    # Ends with open quote
    if text.endswith('"') or text.endswith("'") or text.endswith('\u201c'):
        return True

    # Ends mid-word (hyphenated)
    if re.search(r'[a-z]-$', text):
        return True

    # Ends with a capitalized word (likely mid-title or mid-journal name)
    if re.search(r'\s[A-Z][a-z]+$', text) and not text.endswith('.'):
        if not re.search(r'\.\s*[A-Z][a-z]+$', text):
            return True

    # Doesn't end with sentence-ending punctuation
    if not re.search(r'[.!?)\]\d]$', text):
        if looks_like_author(text) or re.search(r'\(\d{4}\)', text) or re.search(r'[""\u201c\u201d]', text):
            return True

    return False


def is_continuation_line(text: str) -> bool:
    """Check if a line looks like a continuation of a previous reading."""
    text = text.strip()
    if not text:
        return False

    # Use spaCy to check - if this is not a complete sentence on its own,
    # it's more likely to be a continuation
    analyzer = get_semantic_analyzer()
    if analyzer.is_available():
        # Check if this line starts with a new citation (author pattern)
        analysis = analyzer.analyze(text)
        # If it has person entities at the start, it's probably a new citation
        if analysis.get('persons'):
            first_person = analysis['persons'][0] if analysis['persons'] else ''
            if text.startswith(first_person) or text.startswith(first_person.split()[-1]):
                # Looks like a new author - not a continuation
                return False

    # Starts with lowercase (continuation)
    if text[0].islower():
        return True

    # Starts with volume/page info
    if re.match(r'^(Vol\.?|Volume|pp?\.?|Issue|No\.?|Chapter|Ch\.?)\s*\d', text, re.I):
        return True

    # Starts with numbers (page numbers, volume, etc.)
    if re.match(r'^\d+\s*[-–:\(\)]', text):
        return True
    if re.match(r'^\(\d+\)', text):  # (123) - issue number
        return True

    # Starts with journal/publication name patterns
    journal_starts = [
        'Journal', 'Quarterly', 'Review', 'Studies', 'Research', 'Bulletin',
        'Proceedings', 'American', 'British', 'International', 'Annual',
        'European', 'Canadian', 'Australian', 'African', 'Asian', 'Latin',
        'Social', 'Cultural', 'Political', 'Economic', 'Historical',
        'Inquiry', 'Analysis', 'Perspectives', 'Theory', 'Practice',
        'Signs', 'Gender', 'Feminist', 'Women', 'Men', 'Sexuality',
    ]
    if any(text.startswith(j) for j in journal_starts):
        return True

    # Starts with publisher info
    publisher_starts = [
        'Oxford', 'Cambridge', 'Routledge', 'Sage', 'Springer', 'Wiley',
        'University', 'Press', 'Books', 'Publishing', 'Publishers',
        'Harper', 'Random', 'Penguin', 'Basic', 'Free', 'Duke', 'MIT',
        'Harvard', 'Yale', 'Princeton', 'Stanford', 'Chicago', 'California',
        'New York', 'London', 'Boston', 'Philadelphia',
    ]
    if any(text.startswith(p) for p in publisher_starts):
        return True

    # Starts with closing quote or paren
    if text.startswith('"') or text.startswith("'") or text.startswith('\u201d') or text.startswith(')'):
        return True

    # Starts with "ed." or "eds." or "trans." patterns
    if re.match(r'^(ed\.|eds\.|trans\.|translated)', text, re.I):
        return True

    # Starts with continuation words
    if re.match(r'^(and|or|in|of|for|the|a|an)\s', text, re.I):
        return True

    # Short line that looks like citation ending (page numbers, year, etc.)
    if len(text) < 40:
        if re.match(r'^[\d\s\-–:,\(\)\.]+$', text):  # Just numbers and punctuation
            return True
        if re.search(r'^\d+[-–]\d+\.?$', text):  # Page range like "123-456."
            return True

    # Does NOT start with typical author pattern (so probably continuation)
    if not re.match(r'^[A-Z][a-z]+[,\s]+(?:[A-Z]|and|\(|\d{4})', text):
        if re.match(r'^[A-Z][a-z]+', text):
            if not re.search(r'^[A-Z][a-z]+\s*[\(,]\s*\d{4}', text):
                return True

    return False


def should_merge_lines(prev_text: str, next_text: str) -> bool:
    """
    Determine if two lines should be merged using semantic analysis.
    Returns True if lines should be merged.
    """
    # First check: if next line looks like a new citation, don't merge
    # Pattern: Author (Year) or Author, Initial (Year)
    if re.match(r'^[A-Z][a-z]+(?:,\s*[A-Z]\.?)?\s*\(\d{4}\)', next_text):
        return False

    # Check if next line starts with clear author pattern
    if looks_like_author(next_text) and re.search(r'\(\d{4}\)', next_text[:50]):
        return False

    # Use spaCy to check if next line starts with a new author
    analyzer = get_semantic_analyzer()
    if analyzer.is_available():
        analysis = analyzer.analyze(next_text)
        if analysis.get('persons'):
            first_person = analysis['persons'][0] if analysis['persons'] else ''
            # If the next line starts with a person name + year pattern, don't merge
            if first_person and re.match(rf'^{re.escape(first_person.split()[-1])}', next_text):
                if re.search(r'\(\d{4}\)', next_text[:60]):
                    return False

    # If prev ends with terminal punctuation and next starts with caps + year, don't merge
    if prev_text and prev_text[-1] in '.!?)]\u201d"':
        if re.match(r'^[A-Z][a-z]+.*\(\d{4}\)', next_text):
            return False

    # Basic checks: incomplete line + continuation line
    if is_incomplete_line(prev_text) and is_continuation_line(next_text):
        return True

    # Previous line incomplete + next line starts with volume/page
    if is_incomplete_line(prev_text) and re.match(r'^(Vol|pp?|Issue|\d)', next_text, re.I):
        return True

    # Short next line that looks like citation ending
    if len(next_text) < 50 and re.match(r'^[\w\s,]+,?\s*(Vol\.?|pp?\.?|Issue)?\s*\d', next_text, re.I):
        if is_incomplete_line(prev_text):
            return True

    # Use spaCy for additional checks
    if analyzer.is_available():
        # Check if combining them makes a complete sentence
        combined = prev_text + ' ' + next_text
        if not analyzer.is_complete_sentence(prev_text) and analyzer.is_complete_sentence(combined):
            return True

        # Check if prev ends mid-phrase and next completes it
        if prev_text and not prev_text[-1] in '.!?)]\u201d"':
            if next_text and next_text[0].islower():
                return True

    return False


def merge_fragmented_lines(lines: list) -> list:
    """
    Merge lines that were split by PDF copy-paste.
    Uses semantic analysis for smarter merging decisions.
    Returns list of merged line dicts.
    """
    if not lines:
        return []

    merged = []
    current = None

    for item in lines:
        text = item['text'].strip()

        if not text:
            continue

        if current is None:
            current = item.copy()
            current['full_text'] = text
            continue

        # Check if this line should be merged with current
        if should_merge_lines(current['full_text'], text):
            # Merge with current
            current['full_text'] = current['full_text'] + ' ' + text
            current['text'] = current['full_text'][:80] + ('...' if len(current['full_text']) > 80 else '')
            current['end'] = item['end']  # Extend end position
            if DEBUG_MODE:
                print(f"   [DEBUG] Merged lines: ...{current['full_text'][-60:]}")
        else:
            # Save current and start new
            merged.append(current)
            current = item.copy()
            current['full_text'] = text

    # Don't forget the last one
    if current:
        merged.append(current)

    return merged


def merge_fragmented_lines_in_doc(docs_service, doc_id: str) -> int:
    """
    Step 1: Fix PDF line breaks by merging fragmented lines in the actual document.
    Returns count of merged lines.
    """
    print("\n" + "=" * 40)
    print("STEP 1: MERGING FRAGMENTED LINES")
    print("=" * 40)

    doc = docs_service.documents().get(documentId=doc_id).execute()

    # Collect all lines
    raw_lines = []

    def collect_lines(elements):
        for el in elements:
            if 'paragraph' in el:
                para = el['paragraph']
                for pe in para.get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '')
                        start = pe.get('startIndex')
                        end = pe.get('endIndex')

                        if start is None:
                            continue

                        raw_lines.append({
                            'text': text,
                            'text_stripped': normalize_pdf_text(text.strip()),
                            'start': start,
                            'end': end
                        })

            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        collect_lines(cell.get('content', []))

    collect_lines(doc.get('body', {}).get('content', []))
    print(f"   Found {len(raw_lines)} text segments")

    # Find fragments to merge (process in reverse to preserve indices)
    merge_requests = []
    merge_count = 0

    for i in range(len(raw_lines) - 1, 0, -1):
        current = raw_lines[i]
        previous = raw_lines[i - 1]

        current_text = current['text_stripped']
        previous_text = previous['text_stripped']

        if not current_text or not previous_text:
            continue

        # Check if we should merge these lines
        should_merge = False

        if is_incomplete_line(previous_text) and is_continuation_line(current_text):
            should_merge = True

        if is_incomplete_line(previous_text) and re.match(r'^(Vol|pp?|Issue|\d|[a-z])', current_text, re.I):
            should_merge = True

        if should_merge:
            # The break is between previous['end'] and current['start']
            break_start = previous['end'] - 1
            break_end = current['start']

            if break_end > break_start and break_start > 0:
                # Delete newline and insert space
                merge_requests.append({
                    'deleteContentRange': {
                        'range': {'startIndex': break_start, 'endIndex': break_end}
                    }
                })
                merge_requests.append({
                    'insertText': {
                        'location': {'index': break_start},
                        'text': ' '
                    }
                })
                merge_count += 1
                if DEBUG_MODE:
                    print(f"   [DEBUG] Merging: ...{previous_text[-40:]} + {current_text[:40]}...")

    # Execute merge requests
    if merge_requests:
        print(f"   Merging {merge_count} fragmented lines...")
        batch_size = 20
        for i in range(0, len(merge_requests), batch_size):
            batch = merge_requests[i:i + batch_size]
            try:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': batch}
                ).execute()
                time.sleep(0.3)
            except Exception as e:
                print(f"   Warning: Some merges failed: {e}")
        print(f"   ✓ Merged {merge_count} lines")
    else:
        print(f"   No fragmented lines found")

    return merge_count


def find_split_points(text: str) -> list:
    """
    Find positions where a line should be split.
    Returns list of character indices where splits should occur.

    Detects:
    - Numbered lists: 1., 2., 3. or 1), 2), 3) or (1), (2)
    - Lettered lists: a., b., c. or A., B., C. or a), b)
    - Bullet points: •, -, *, ◦
    - New citations starting mid-line (Author (Year) pattern)
    """
    split_points = []

    # Patterns that indicate a new list item (should have newline before)
    # These patterns look for item markers that appear AFTER some content
    patterns = [
        # Numbered: "...text 1. new item" or "...text 1) new item"
        r'(?<=[.!?)\]\"\'\s])\s*(\d{1,2})[.\)]\s+(?=[A-Z])',
        # Numbered with parentheses: "...text (1) new item"
        r'(?<=[.!?)\]\"\'\s])\s*\((\d{1,2})\)\s*(?=[A-Z])',
        # Lettered: "...text a. new item" or "...text A) new item"
        r'(?<=[.!?)\]\"\'\s])\s*([a-zA-Z])[.\)]\s+(?=[A-Z])',
        # Bullet points
        r'(?<=[.!?)\]\"\'\s])\s*([•\-\*◦])\s+(?=[A-Z])',
        # New citation pattern: "...text. Author (Year)" or "...text; Author (Year)"
        r'(?<=[.;!?])\s+(?=[A-Z][a-z]+(?:,\s*[A-Z]\.?)?\s*(?:et al\.?)?\s*\(\d{4})',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            # Get the position just before the number/letter/bullet
            pos = match.start()
            if pos > 10:  # Only split if there's substantial content before
                split_points.append(pos)

    # Remove duplicates and sort
    split_points = sorted(set(split_points))

    # Filter out split points that are too close together (< 30 chars)
    filtered = []
    last_pos = -30
    for pos in split_points:
        if pos - last_pos >= 30:
            filtered.append(pos)
            last_pos = pos

    return filtered


def split_concatenated_lines_in_doc(docs_service, doc_id: str) -> int:
    """
    Split lines that contain multiple readings concatenated together.
    Detects numbered lists, bullet points, and citation patterns.
    Returns count of splits made.
    """
    print("\n" + "-" * 40)
    print("SPLITTING CONCATENATED LINES")
    print("-" * 40)

    doc = docs_service.documents().get(documentId=doc_id).execute()

    # Collect all paragraphs
    paragraphs = []

    def collect_paragraphs(elements):
        for el in elements:
            if 'paragraph' in el:
                para = el['paragraph']
                full_text = ''
                start_idx = None
                end_idx = None

                for pe in para.get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '')
                        s = pe.get('startIndex')
                        e = pe.get('endIndex')

                        if s is not None:
                            if start_idx is None:
                                start_idx = s
                            end_idx = e
                            full_text += text

                if full_text.strip() and start_idx is not None:
                    paragraphs.append({
                        'text': full_text,
                        'start': start_idx,
                        'end': end_idx
                    })

            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        collect_paragraphs(cell.get('content', []))

    collect_paragraphs(doc.get('body', {}).get('content', []))
    print(f"   Found {len(paragraphs)} paragraphs to analyze")

    # Find paragraphs that need splitting (process in reverse order)
    split_requests = []
    split_count = 0

    for para in reversed(paragraphs):
        text = para['text']
        base_start = para['start']

        # Find split points within this paragraph
        local_splits = find_split_points(text)

        if local_splits:
            if DEBUG_MODE:
                print(f"   [DEBUG] Found {len(local_splits)} split points in: {text[:60]}...")

            # Process splits in reverse order within the paragraph
            for local_pos in reversed(local_splits):
                doc_pos = base_start + local_pos

                # Insert a newline at this position
                split_requests.append({
                    'insertText': {
                        'location': {'index': doc_pos},
                        'text': '\n'
                    }
                })
                split_count += 1

    # Execute split requests
    if split_requests:
        print(f"   Inserting {split_count} line breaks...")
        batch_size = 20
        for i in range(0, len(split_requests), batch_size):
            batch = split_requests[i:i + batch_size]
            try:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': batch}
                ).execute()
                time.sleep(0.3)
            except Exception as e:
                print(f"   Warning: Some splits failed: {e}")
        print(f"   ✓ Split {split_count} concatenated lines")
    else:
        print(f"   No concatenated lines found")

    return split_count


def clean_syllabus(docs_service, doc_id: str) -> dict:
    """
    Step 2: Classify syllabus content (after lines have been merged).
    Returns classification stats.
    """
    print("\n" + "=" * 40)
    print("STEP 2: CLASSIFYING CONTENT")
    print("=" * 40)

    doc = docs_service.documents().get(documentId=doc_id).execute()

    stats = {
        'headers': [],
        'readings': [],
        'instructions': [],
        'uncertain': [],
        'too_short': [],
        'urls': [],
        'split_readings': [],  # Readings that were split from concatenated text
        'merged_lines': 0  # Count of lines that were merged
    }

    current_week = [0]  # Use list to allow modification in nested function

    def classify_single_text(text: str, start: int, end: int, is_split: bool = False):
        """Classify a single text segment using combined scoring and semantic analysis."""
        # Get reading score for analysis
        score, reasons = get_reading_score(text)

        # Also get instruction score
        instr_score, _ = get_instruction_score(text)

        # Get semantic classification for additional insight (used for uncertain cases)
        analyzer = get_semantic_analyzer()
        semantic_class, semantic_conf = 'unknown', 0.0
        if analyzer.is_available():
            semantic_class, semantic_conf, _ = analyzer.classify_text_type(text)

        item = {
            'text': text[:80] + ('...' if len(text) > 80 else ''),
            'full_text': text,
            'start': start,
            'end': end,
            'week': current_week[0],
            'was_split': is_split,
            'score': score,
            'instr_score': instr_score,
            'semantic_class': semantic_class,
            'semantic_conf': semantic_conf,
            'reasons': reasons
        }

        # Check for URL
        if extract_url(text):
            item['has_url'] = True
            stats['urls'].append(item)

        # Debug output
        if DEBUG_MODE:
            print(f"\n   [DEBUG] Text: {text[:100]}{'...' if len(text) > 100 else ''}")
            print(f"   [DEBUG] Length: {len(text)}, Reading Score: {score}, Instruction Score: {instr_score}")
            print(f"   [DEBUG] Semantic: {semantic_class} (conf: {semantic_conf:.2f})")
            print(f"   [DEBUG] Reading reasons: {', '.join(reasons) if reasons else 'none'}")
            print(f"   [DEBUG] is_header: {is_header(text)}, is_instruction: {is_instruction(text)}")

        # Classify
        if len(text) < 20:
            if DEBUG_MODE:
                print(f"   [DEBUG] -> Classified as: TOO_SHORT")
            stats['too_short'].append(item)
        elif is_header(text):
            week = is_week_header(text)
            if week:
                current_week[0] = week
                item['week'] = week
            if DEBUG_MODE:
                print(f"   [DEBUG] -> Classified as: HEADER (week={week})")
            stats['headers'].append(item)
        elif is_instruction(text):
            if DEBUG_MODE:
                print(f"   [DEBUG] -> Classified as: INSTRUCTION")
            stats['instructions'].append(item)
        elif score >= 3:  # Use score directly instead of is_reading()
            item['week'] = current_week[0]
            if is_split:
                stats['split_readings'].append(item)
            if DEBUG_MODE:
                print(f"   [DEBUG] -> Classified as: READING (score >= 3)")
            stats['readings'].append(item)
        elif score >= 1:
            # Low confidence - might be a reading
            # Check if this might be concatenated readings (PDF copy-paste)
            split_texts = split_concatenated_readings(text)
            if len(split_texts) > 1:
                # Found multiple readings in one block
                print(f"   📋 Found {len(split_texts)} concatenated readings in one line")
                for split_text in split_texts:
                    # Recursively classify each split segment
                    classify_single_text(split_text.strip(), start, end, is_split=True)
            else:
                # Use semantic classification to help decide
                # If semantic analysis says it's a reading with high confidence, promote it
                if semantic_class == 'reading' and semantic_conf >= 0.6:
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: READING (semantic boost: conf {semantic_conf:.2f})")
                    item['week'] = current_week[0]
                    item['semantic_boosted'] = True
                    stats['readings'].append(item)
                elif semantic_class == 'instruction' and semantic_conf >= 0.6:
                    # Semantic says instruction - classify as instruction
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: INSTRUCTION (semantic: conf {semantic_conf:.2f})")
                    stats['instructions'].append(item)
                else:
                    # Low confidence reading - add to uncertain
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: MAYBE_READING (score 1-2)")
                    item['classification'] = 'maybe_reading'
                    stats['uncertain'].append(item)
        else:
            # Check if this might be concatenated readings (PDF copy-paste)
            split_texts = split_concatenated_readings(text)
            if len(split_texts) > 1:
                print(f"   📋 Found {len(split_texts)} concatenated readings in one line")
                for split_text in split_texts:
                    classify_single_text(split_text.strip(), start, end, is_split=True)
            else:
                # Use semantic classification as final arbiter for edge cases
                if semantic_class == 'reading' and semantic_conf >= 0.7:
                    # Semantic strongly suggests reading despite low score
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: READING (semantic override: conf {semantic_conf:.2f})")
                    item['week'] = current_week[0]
                    item['semantic_boosted'] = True
                    stats['readings'].append(item)
                elif semantic_class == 'instruction' and semantic_conf >= 0.5:
                    # Semantic says instruction
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: INSTRUCTION (semantic: conf {semantic_conf:.2f})")
                    stats['instructions'].append(item)
                else:
                    # Truly uncertain / not a reading
                    if DEBUG_MODE:
                        print(f"   [DEBUG] -> Classified as: UNKNOWN (score <= 0)")
                    item['classification'] = 'unknown'
                    stats['uncertain'].append(item)

    def collect_raw_lines(elements) -> list:
        """Collect all raw text lines from document elements."""
        lines = []
        for el in elements:
            if 'paragraph' in el:
                para = el['paragraph']
                for pe in para.get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '').strip()
                        start = pe.get('startIndex')
                        end = pe.get('endIndex')

                        if not text or start is None:
                            continue

                        # Normalize PDF text
                        text = normalize_pdf_text(text)

                        lines.append({
                            'text': text,
                            'start': start,
                            'end': end
                        })

            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        lines.extend(collect_raw_lines(cell.get('content', [])))

        return lines

    def classify_line(item):
        """Classify a single line (after merging)."""
        text = item.get('full_text', item['text'])
        start = item['start']
        end = item['end']

        # Try to split if text is long or has multiple author patterns
        if len(text) > 60:
            pairs = extract_author_year_pairs(text)
            author_like_count = len(re.findall(r'(?:^|[.;]\s+)([A-Z][a-z]+)', text))

            if len(pairs) > 1 or author_like_count > 2:
                split_texts = split_concatenated_readings(text)
                if len(split_texts) > 1:
                    print(f"   📋 Splitting line with {len(split_texts)} readings")
                    for split_text in split_texts:
                        classify_single_text(split_text.strip(), start, end, is_split=True)
                    return

        # Normal classification
        classify_single_text(text, start, end)

    # Step 1: Collect all raw lines
    raw_lines = collect_raw_lines(doc.get('body', {}).get('content', []))
    print(f"   Found {len(raw_lines)} raw text lines")

    # Step 2: Merge fragmented lines (PDF line break fix)
    merged_lines = merge_fragmented_lines(raw_lines)
    merge_count = len(raw_lines) - len(merged_lines)
    if merge_count > 0:
        print(f"   Merged {merge_count} fragmented lines -> {len(merged_lines)} lines")
        stats['merged_lines'] = merge_count

    # Step 3: Classify each merged line
    for item in merged_lines:
        classify_line(item)

    # Print classification summary
    print(f"\n   Classification Summary:")
    if stats['merged_lines'] > 0:
        print(f"   ├── Merged lines: {stats['merged_lines']} (PDF line break fixes)")
    print(f"   ├── Headers:      {len(stats['headers'])}")
    print(f"   ├── Readings:     {len(stats['readings'])}")
    if stats['split_readings']:
        print(f"   │   └── (Split from concatenated: {len(stats['split_readings'])})")
    print(f"   ├── Instructions: {len(stats['instructions'])}")
    print(f"   ├── With URLs:    {len(stats['urls'])}")
    print(f"   ├── Uncertain:    {len(stats['uncertain'])}")
    print(f"   └── Too short:    {len(stats['too_short'])}")

    # Show split readings if any (from PDF copy-paste)
    if stats['split_readings']:
        print(f"\n   📋 Split readings (detected from concatenated text):")
        for i, item in enumerate(stats['split_readings'][:5]):
            week_str = f"Week {item['week']}" if item['week'] > 0 else "No week"
            print(f"      {i+1}. [{week_str}] {item['text']}")
        if len(stats['split_readings']) > 5:
            print(f"      ... and {len(stats['split_readings']) - 5} more")

    # Show uncertain items with scores (these might need review)
    if stats['uncertain']:
        # Separate maybe-readings from unknown
        maybe_readings = [i for i in stats['uncertain'] if i.get('classification') == 'maybe_reading']
        unknowns = [i for i in stats['uncertain'] if i.get('classification') == 'unknown']

        if maybe_readings:
            print(f"\n   ⚠ Low-confidence readings (score 1-2, may need review):")
            for i, item in enumerate(maybe_readings[:5]):
                score = item.get('score', 0)
                reasons = ', '.join(item.get('reasons', [])[:3])
                print(f"      {i+1}. [score:{score}] {item['text']}")
                if reasons:
                    print(f"         Signals: {reasons}")
            if len(maybe_readings) > 5:
                print(f"      ... and {len(maybe_readings) - 5} more")

        if unknowns:
            print(f"\n   ❓ Unknown items (score 0 or less):")
            for i, item in enumerate(unknowns[:5]):
                print(f"      {i+1}. {item['text']}")
            if len(unknowns) > 5:
                print(f"      ... and {len(unknowns) - 5} more")

    # Show detected readings with confidence
    if stats['readings']:
        print(f"\n   ✓ Detected readings (score >= 3):")
        for i, item in enumerate(stats['readings'][:10]):
            week_str = f"Week {item['week']}" if item['week'] > 0 else "No week"
            split_marker = " [split]" if item.get('was_split') else ""
            score = item.get('score', 0)
            print(f"      {i+1}. [{week_str}] [score:{score}] {item['text']}{split_marker}")
        if len(stats['readings']) > 10:
            print(f"      ... and {len(stats['readings']) - 10} more")

    return stats


def format_syllabus(docs_service, doc_id: str):
    """
    Step 3: Apply visual styles based on content classification.
    Should be run AFTER merge and clean steps.
    """
    print("\n" + "=" * 40)
    print("STEP 3: APPLYING VISUAL STYLES")
    print("=" * 40)

    doc = docs_service.documents().get(documentId=doc_id).execute()

    # Style definitions for different content types
    styles = {
        'week_header': {
            'bold': True,
            'fontSize': {'magnitude': 14, 'unit': 'PT'},
            'foregroundColor': {'color': {'rgbColor': {'red': 0.1, 'green': 0.3, 'blue': 0.6}}}  # Blue
        },
        'section_header': {
            'bold': True,
            'fontSize': {'magnitude': 12, 'unit': 'PT'},
            'foregroundColor': {'color': {'rgbColor': {'red': 0.2, 'green': 0.2, 'blue': 0.2}}}  # Dark gray
        },
        'reading': {
            'bold': False,
            'fontSize': {'magnitude': 11, 'unit': 'PT'},
            'foregroundColor': {'color': {'rgbColor': {'red': 0.0, 'green': 0.4, 'blue': 0.0}}}  # Dark green
        },
        'instruction': {
            'bold': False,
            'fontSize': {'magnitude': 10, 'unit': 'PT'},
            'foregroundColor': {'color': {'rgbColor': {'red': 0.5, 'green': 0.5, 'blue': 0.5}}}  # Gray
        },
        'uncertain': {
            'bold': False,
            'fontSize': {'magnitude': 11, 'unit': 'PT'},
            'foregroundColor': {'color': {'rgbColor': {'red': 0.8, 'green': 0.4, 'blue': 0.0}}}  # Orange
        }
    }

    format_requests = []
    counts = {'week_header': 0, 'section_header': 0, 'reading': 0, 'instruction': 0, 'uncertain': 0}

    def apply_styles(elements):
        for el in elements:
            if 'paragraph' in el:
                para = el['paragraph']
                for pe in para.get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '').strip()
                        start = pe.get('startIndex')
                        end = pe.get('endIndex')

                        if not text or start is None:
                            continue

                        # Normalize text for classification
                        text_norm = normalize_pdf_text(text)

                        # Determine content type and apply style
                        style = None
                        style_type = None
                        style_fields = 'bold,fontSize,foregroundColor'

                        if is_week_header(text_norm):
                            style = styles['week_header']
                            style_type = 'week_header'
                        elif is_header(text_norm):
                            style = styles['section_header']
                            style_type = 'section_header'
                        elif is_instruction(text_norm):
                            style = styles['instruction']
                            style_type = 'instruction'
                        elif is_reading(text_norm):
                            style = styles['reading']
                            style_type = 'reading'
                        else:
                            score, _ = get_reading_score(text_norm)
                            if score >= 1:
                                style = styles['uncertain']
                                style_type = 'uncertain'

                        if style:
                            counts[style_type] += 1
                            format_requests.append({
                                'updateTextStyle': {
                                    'range': {'startIndex': start, 'endIndex': end},
                                    'textStyle': style,
                                    'fields': style_fields
                                }
                            })

            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        apply_styles(cell.get('content', []))

    apply_styles(doc.get('body', {}).get('content', []))

    # Execute formatting requests
    if format_requests:
        print(f"   Applying styles to {len(format_requests)} text segments...")
        batch_size = 50
        for i in range(0, len(format_requests), batch_size):
            batch = format_requests[i:i + batch_size]
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': batch}
            ).execute()
            time.sleep(0.5)

    # Summary
    print(f"\n   ✓ Styling complete:")
    print(f"   ├── Week headers:    {counts['week_header']} (Bold, Blue)")
    print(f"   ├── Section headers: {counts['section_header']} (Bold, Dark Gray)")
    print(f"   ├── Readings:        {counts['reading']} (Dark Green)")
    print(f"   ├── Instructions:    {counts['instruction']} (Gray)")
    print(f"   └── Uncertain:       {counts['uncertain']} (Orange - review these!)")


def organize_drive_folder(drive_service, docs_service, doc_id: str, folder_id: str):
    """Organize Drive folder with week subfolders and renamed files."""
    print("\nOrganizing Google Drive folder...")

    # Get document content to map readings to weeks
    doc = docs_service.documents().get(documentId=doc_id).execute()

    reading_to_week = {}  # Map reading text -> week number
    current_week = 0

    def process_elements(elements):
        nonlocal current_week
        for el in elements:
            if 'paragraph' in el:
                for pe in el['paragraph'].get('elements', []):
                    if 'textRun' in pe:
                        text = pe['textRun'].get('content', '').strip()
                        if not text:
                            continue

                        week = is_week_header(text)
                        if week:
                            current_week = week
                        elif is_reading(text) and current_week > 0:
                            # Check if this reading has a link
                            link = pe['textRun'].get('textStyle', {}).get('link', {}).get('url', '')
                            if link and 'drive.google.com' in link:
                                # Extract file ID from Drive link
                                file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
                                if file_id_match:
                                    file_id = file_id_match.group(1)
                                    reading_to_week[file_id] = {
                                        'week': current_week,
                                        'text': text
                                    }
            elif 'table' in el:
                for row in el['table'].get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        process_elements(cell.get('content', []))

    process_elements(doc.get('body', {}).get('content', []))

    if not reading_to_week:
        print("   No linked readings found to organize")
        return

    print(f"   Found {len(reading_to_week)} linked readings")

    # Create week folders and move files
    week_folders = {}  # week number -> folder id
    moved = 0
    renamed = 0

    for file_id, info in reading_to_week.items():
        week = info['week']
        text = info['text']

        try:
            # Get current file info
            file_info = drive_service.files().get(
                fileId=file_id,
                fields='name,parents'
            ).execute()
            current_name = file_info.get('name', '')
            current_parents = file_info.get('parents', [])

            # Get or create week folder
            if week not in week_folders:
                folder_name = f"Week {week}"
                week_folders[week] = get_or_create_folder(drive_service, folder_id, folder_name)

            week_folder_id = week_folders[week]

            # Generate new filename
            new_name = extract_author_title(text)
            if not new_name.endswith('.pdf'):
                new_name += '.pdf'

            # Build update request
            update_body = {}

            # Rename if different
            if current_name != new_name:
                update_body['name'] = new_name
                renamed += 1

            # Move if not already in week folder
            if week_folder_id not in current_parents:
                # Move file to week folder
                drive_service.files().update(
                    fileId=file_id,
                    addParents=week_folder_id,
                    removeParents=','.join(current_parents),
                    body=update_body if update_body else None,
                    fields='id'
                ).execute()
                moved += 1
                print(f"   Moved to Week {week}: {new_name[:40]}...")
            elif update_body:
                # Just rename
                drive_service.files().update(
                    fileId=file_id,
                    body=update_body,
                    fields='id'
                ).execute()
                print(f"   Renamed: {new_name[:40]}...")

            time.sleep(0.3)  # Rate limiting

        except Exception as e:
            print(f"   Error organizing file {file_id}: {e}")

    print(f"   Moved {moved} files, renamed {renamed} files")


def download_readings(docs, drive, doc_id: str, folder_id: str, email: str = None):
    """Download PDFs and add links to document."""
    # Load progress
    done = load_progress(doc_id)
    if done:
        print(f"Resuming: {len(done)} items already processed")

    # Get existing PDFs in Drive folder
    print("\nScanning Drive folder for existing PDFs...")
    existing_pdfs = list_drive_pdfs(drive, folder_id)
    print(f"Found {len(existing_pdfs)} existing PDFs in Drive")

    # Get document
    print("\nReading document...")
    lines = get_doc_content(docs, doc_id)
    print(f"Found {len(lines)} text lines")

    # Stats
    found, failed, web_links, matched = 0, 0, 0, 0

    # Process in reverse (to avoid index drift)
    for i, item in enumerate(reversed(lines)):
        text = item['text']

        if not is_reading(text):
            continue

        if item['start'] in done:
            continue

        print(f"\n[{len(lines)-i}/{len(lines)}] {text[:60]}...")

        # Check for URL in text first (web-based readings)
        url = extract_url(text)
        if url:
            print(f"   Found URL: {url[:50]}...")
            try:
                add_link_to_doc(docs, doc_id, item['start'], item['end'], url)
                print(f"   Linked directly to URL!")
                web_links += 1
                done.add(item['start'])
                save_progress(doc_id, done)
                time.sleep(0.5)
                continue
            except Exception as e:
                print(f"   Error adding URL link: {e}")

        # Check if PDF already exists in Drive
        if existing_pdfs:
            match = match_pdf_to_reading(text, existing_pdfs)
            if match:
                print(f"   Matched existing PDF: {match['name'][:40]}...")
                try:
                    add_link_to_doc(docs, doc_id, item['start'], item['end'], match['link'])
                    print(f"   Linked to existing PDF!")
                    matched += 1
                    done.add(item['start'])
                    save_progress(doc_id, done)
                    time.sleep(0.5)
                    continue
                except Exception as e:
                    print(f"   Error adding link: {e}")

        # Find PDF from academic sources
        local_path = find_pdf(text, email)

        if not local_path:
            print(f"   No PDF found - skipping")
            failed += 1
            done.add(item['start'])
            save_progress(doc_id, done)
            time.sleep(1)
            continue

        # Upload to Drive
        link = upload_to_drive(drive, local_path, folder_id)

        if link:
            try:
                add_link_to_doc(docs, doc_id, item['start'], item['end'], link)
                print(f"   Linked!")
                found += 1
                done.add(item['start'])
                save_progress(doc_id, done)
            except Exception as e:
                print(f"   Error adding link: {e}")
                failed += 1
        else:
            print(f"   Drive upload failed - no link added")
            failed += 1

        time.sleep(1)  # Rate limiting

    return found, failed, web_links, matched


def main():
    parser = argparse.ArgumentParser(description='Syllabus Organizer - Download PDFs, format docs, organize Drive')
    parser.add_argument('--merge', '-m', action='store_true', help='Step 1: Merge fragmented lines & split numbered lists')
    parser.add_argument('--clean', '-c', action='store_true', help='Step 2: Classify content (readings vs non-readings)')
    parser.add_argument('--format', '-f', action='store_true', help='Step 3: Apply visual styles based on content type')
    parser.add_argument('--download', '-d', action='store_true', help='Step 4: Download PDFs and add links')
    parser.add_argument('--organize', '-o', action='store_true', help='Step 5: Organize Drive folder by week')
    parser.add_argument('--all', '-a', action='store_true', help='Run all operations')
    parser.add_argument('--reset', action='store_true', help='Clear progress and start fresh')
    parser.add_argument('--debug', action='store_true', help='Show detailed debug output')
    args = parser.parse_args()

    # Store debug flag globally
    global DEBUG_MODE
    DEBUG_MODE = args.debug

    # Default to --all if no options specified
    if not any([args.merge, args.clean, args.download, args.format, args.organize, args.all, args.reset]):
        args.all = True

    print("=" * 50)
    print("Syllabus Organizer")
    print("=" * 50)

    # Load config
    config = load_config()
    doc_id = config.get('DOC_ID')
    folder_id = config.get('FOLDER_ID')
    email = config.get('EMAIL')

    if not doc_id or not folder_id:
        print("Error: Missing DOC_ID or FOLDER_ID in config.txt")
        return

    # Handle reset
    if args.reset:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            print("Progress cleared!")
        return

    # Authenticate
    print("\nAuthenticating...")
    creds = authenticate()
    docs = build('docs', 'v1', credentials=creds)
    drive = build('drive', 'v3', credentials=creds)
    print("Authenticated!")

    # Run operations in order: merge -> clean -> format -> download -> organize

    # Step 1: Merge and split lines (fix PDF copy-paste issues)
    if args.merge or args.all:
        merge_count = merge_fragmented_lines_in_doc(docs, doc_id)
        split_count = split_concatenated_lines_in_doc(docs, doc_id)

    # Step 2: Classify content (after merging)
    if args.clean or args.all:
        stats = clean_syllabus(docs, doc_id)

    # Step 3: Apply visual styles
    if args.format or args.all:
        format_syllabus(docs, doc_id)

    # Step 4: Download PDFs and add links
    if args.download or args.all:
        print("\n" + "=" * 40)
        print("STEP 4: DOWNLOADING READINGS")
        print("=" * 40)
        found, failed, web_links, matched = download_readings(docs, drive, doc_id, folder_id, email)
        print(f"\n   ✓ Download complete:")
        print(f"   ├── New PDFs:        {found}")
        print(f"   ├── Matched existing: {matched}")
        print(f"   ├── Web links:       {web_links}")
        print(f"   └── Not found:       {failed}")

    # Step 5: Organize Drive folder
    if args.organize or args.all:
        print("\n" + "=" * 40)
        print("STEP 5: ORGANIZING DRIVE FOLDER")
        print("=" * 40)
        organize_drive_folder(drive, docs, doc_id, folder_id)

    # Summary
    print("\n" + "=" * 50)
    print("All done!")
    print(f"View doc: https://docs.google.com/document/d/{doc_id}/edit")


if __name__ == '__main__':
    main()
