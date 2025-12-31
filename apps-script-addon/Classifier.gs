/**
 * Text Classification Module
 * Ports regex patterns from Python organizer.py for detecting readings, headers, and instructions
 *
 * Expected accuracy: 70-75% (without NLP/spaCy)
 */

/**
 * Check if text starts with what looks like an author name
 * Ported from organizer.py lines 401-431
 */
function looksLikeAuthor(text) {
  text = text.trim();
  if (!text) return false;

  const authorPatterns = [
    /^[A-Z][a-z]+/,                                    // Simple: Smith
    /^[A-Z][''][A-Z]?[a-z]+/,                          // O'Brien, O'Connor
    /^(?:van|von|de|del|la|le|du|dos|das)\s+[A-Z]/,   // van Gogh, de Silva
    /^Mc[A-Z][a-z]+/,                                  // McDonald
    /^Mac[A-Z][a-z]+/,                                 // MacArthur
    /^[A-Z][a-z]+,\s*[A-Z]/,                          // Last, First
    /^[A-Z][a-z]+\s+(?:and|&)\s+[A-Z][a-z]+/,         // Smith and Jones
    /^[A-Z][a-z]+\s+et\s+al/                          // Smith et al
  ];

  return authorPatterns.some(pattern => pattern.test(text));
}

/**
 * Check if text is a section header (week, topic, etc.)
 * Ported from organizer.py lines 771-833
 */
function isHeader(text) {
  const textLower = text.toLowerCase().trim();
  const textClean = textLower.replace(/^[\d\.\)\-•*]+\s*/, '');  // Remove leading bullets

  // Course title patterns (e.g., "WGST 224:" or "SOC 101 -")
  if (/^[A-Z]{2,5}\s*\d{2,4}[:\s\-]/.test(text.trim())) {
    return true;
  }

  // Semester/term in brackets
  if (/\[(spring|fall|summer|winter)\s+\d{4}\]/.test(textLower)) {
    return true;
  }
  if (/\((spring|fall|summer|winter)\s+\d{4}\)/.test(textLower)) {
    return true;
  }

  // Week headers
  if (/^week\s*\d+/.test(textClean)) {
    return true;
  }

  // Session/Class/Module headers
  if (/^(session|class|module|unit|part|section|lecture|seminar|meeting|day)\s*\d+/.test(textClean)) {
    return true;
  }

  // Date headers (e.g., "October 15" or "10/15")
  const months = 'january|february|march|april|may|june|july|august|september|october|november|december';
  const monthsAbbr = 'jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec';
  const monthRegex = new RegExp(`^(${months}|${monthsAbbr})\\.?\\s+\\d{1,2}`, 'i');
  if (monthRegex.test(textClean)) {
    return true;
  }
  if (/^\d{1,2}\/\d{1,2}(\/\d{2,4})?$/.test(textClean)) {
    return true;
  }

  // Day of week headers
  if (/^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)/.test(textClean)) {
    return true;
  }

  // Topic/Section header keywords
  const headerKeywords = [
    'introduction', 'overview', 'conclusion', 'review', 'midterm', 'final',
    'exam', 'break', 'holiday', 'no class', 'thanksgiving', 'spring break',
    'readings', 'required readings', 'recommended readings', 'optional readings',
    'assignments', 'topics', 'schedule', 'theme', 'topic',
    'course policies', 'policies', 'grading', 'grade breakdown',
    'office hours', 'contact', 'instructor', 'professor', 'ta ',
    'teaching assistant', 'course objectives', 'learning objectives',
    'course description', 'description', 'prerequisites', 'materials',
    'required materials', 'textbooks', 'books', 'resources'
  ];

  for (const kw of headerKeywords) {
    if (textClean === kw ||
        textClean.startsWith(kw + ':') ||
        textClean.startsWith(kw + ' -')) {
      return true;
    }
  }

  // All caps short text (likely header)
  if (text.length < 60 && text.replace(/\s/g, '').toUpperCase() === text.replace(/\s/g, '') && text.length > 3) {
    return true;
  }

  // Short text ending with colon (likely header)
  if (text.length < 40 && text.endsWith(':')) {
    return true;
  }

  // Roman numeral headers: "I.", "II.", "III." etc.
  if (/^[IVX]+\.\s/.test(text)) {
    return true;
  }

  return false;
}

/**
 * Calculate confidence score for whether text is a reading
 * Ported from organizer.py lines 836-935
 * Returns {score: number, reasons: string[]}
 */
function getReadingScore(text) {
  text = text.trim();
  let score = 0;
  const reasons = [];

  // Remove leading bullets/numbers for analysis
  const textClean = text.replace(/^[\d\.\)\-•*]+\s*/, '');

  // === STRONG INDICATORS (+3 each) ===
  const strongPatterns = [
    { pattern: /^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*[\(,]\s*\d{4}/, reason: "Author (Year)" },
    { pattern: /^[A-Z][a-z]+\s+et\s+al\.?\s*[\(,]?\s*\d{4}/, reason: "Author et al. (Year)" },
    { pattern: /^[A-Z][a-z]+,\s*[A-Z][a-z\.]+\s*[\(,]\s*\d{4}/, reason: "Last, First (Year)" },
    { pattern: /[""\u201c][^"""\u201d]{20,}[""\u201d]/, reason: "Quoted title" }
  ];

  strongPatterns.forEach(({ pattern, reason }) => {
    if (pattern.test(textClean)) {
      score += 3;
      reasons.push(`+3 ${reason}`);
    }
  });

  // === MEDIUM INDICATORS (+1 each) ===
  const mediumPatterns = [
    { pattern: /\(\d{4}\)/, reason: "Year in parens" },
    { pattern: /,\s*\d{4}[,.\s]/, reason: "Year after comma" },
    { pattern: /pp?\.?\s*\d+[-–]?\d*/, reason: "Page numbers" },
    { pattern: /vol\.?\s*\d+/i, reason: "Volume" },
    { pattern: /no\.?\s*\d+/i, reason: "Issue number" },
    { pattern: /\bch(?:apter)?\.?\s*\d+/i, reason: "Chapter" },
    { pattern: /["''\u201c\u201d].{15,}["''\u201c\u201d]/, reason: "Quoted text" },
    { pattern: /\b[Ee]d(?:s|ited)?\.?\s*(?:by)?\s*[A-Z]/, reason: "Editor" },
    { pattern: /\b[Tt]rans(?:lated)?\.?\s*(?:by)?\s*[A-Z]/, reason: "Translator" },
    { pattern: /[Uu]niversity\s+[Pp]ress/, reason: "University Press" },
    { pattern: /[Jj]ournal\s+of\s+[A-Z]/, reason: "Journal of..." },
    { pattern: /\b(?:Quarterly|Review|Studies|Bulletin|Proceedings)\s+(?:of\s+)?[A-Z]/, reason: "Academic journal" },
    { pattern: /\b(?:Oxford|Cambridge|Routledge|Sage|Springer|Wiley|Penguin|Harvard|Yale|Princeton)\b/i, reason: "Major publisher" },
    { pattern: /\b(?:ISBN|DOI)\b|doi\.org|doi:\s*10\./i, reason: "Identifier" },
    { pattern: /\(\d+\):\s*\d+[-–]?\d*/, reason: "Vol(issue): pages" },
    { pattern: /\bIn:\s+[A-Z][a-z]+/, reason: "In: anthology" },
    { pattern: /\bed\.\s+by\s+[A-Z]|\bedited\s+by\s+[A-Z]/, reason: "Edited by" },
    { pattern: /excerpts?\s+from|selections?\s+from/i, reason: "Excerpt/selection" }
  ];

  mediumPatterns.forEach(({ pattern, reason }) => {
    if (pattern.test(textClean)) {
      score += 1;
      reasons.push(`+1 ${reason}`);
    }
  });

  // Author name bonus (+2)
  if (looksLikeAuthor(textClean)) {
    score += 2;
    reasons.push("+2 Starts with author name");
  }

  // Length bonus (+1)
  if (textClean.length > 80) {
    score += 1;
    reasons.push("+1 Substantial length");
  }

  // === NEGATIVE INDICATORS ===
  const negativePatterns = [
    { pattern: /^(https?:\/\/|www\.)\S+$/, reason: "URL only", penalty: -2 },
    { pattern: /^\d+\s*(%|percent|points?)/, reason: "Grading info", penalty: -2 },
    { pattern: /^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b/, reason: "Day of week", penalty: -2 },
    { pattern: /^\d{1,2}[:/]\d{2}/, reason: "Time", penalty: -2 },
    { pattern: /\bthis course\b/i, reason: "Course description", penalty: -3 },
    { pattern: /\bthe course\b/i, reason: "Course description", penalty: -3 },
    { pattern: /\bthis class\b/i, reason: "Course description", penalty: -3 },
    { pattern: /\bstudents will\b/i, reason: "Course description", penalty: -3 },
    { pattern: /\bstudents learn\b/i, reason: "Course description", penalty: -3 },
    { pattern: /\bwe will\b/i, reason: "Course description", penalty: -2 },
    { pattern: /\boffice hours\b/i, reason: "Office hours", penalty: -3 },
    { pattern: /\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}/, reason: "Time range", penalty: -2 },
    { pattern: /\bwhat is\b.*\?/i, reason: "Question", penalty: -2 },
    { pattern: /\bhow do\b.*\?/i, reason: "Question", penalty: -2 },
    { pattern: /\bin person\b/i, reason: "Meeting format", penalty: -2 }
  ];

  negativePatterns.forEach(({ pattern, reason, penalty }) => {
    if (pattern.test(textClean)) {
      score += penalty;
      reasons.push(`${penalty} ${reason}`);
    }
  });

  return { score, reasons };
}

/**
 * Check if text is a reading (binary decision)
 * Returns true if score >= 3
 */
function isReading(text) {
  if (text.length < 20) return false;
  if (isHeader(text) || isInstruction(text)) return false;

  const { score } = getReadingScore(text);
  return score >= 3;
}

/**
 * Calculate confidence score for whether text is an instruction
 * Ported from organizer.py lines 638-750
 * Returns {score: number, reasons: string[]}
 */
function getInstructionScore(text) {
  text = text.trim();
  let score = 0;
  const reasons = [];

  // Remove leading bullets/numbers for analysis
  const textClean = text.replace(/^[\d\.\)\-•*]+\s*/, '');
  const textLower = textClean.toLowerCase();

  // === STRONG INSTRUCTION STARTERS (+3 each) ===
  const strongStarters = [
    { pattern: /^(read|write|submit|complete|prepare|review|discuss|bring|post|upload|email|send)\s/, reason: "Imperative verb start" },
    { pattern: /^(please|note:|note that|you should|you will|you must)\b/, reason: "Polite instruction" },
    { pattern: /^(students will|students should|students must)\b/, reason: "Student directive" },
    { pattern: /^(be prepared|come prepared|make sure|don't forget|remember to)\b/, reason: "Preparation instruction" },
    { pattern: /^(assignment|homework|essay|paper due|exam|quiz|midterm|final)\b/, reason: "Assignment/exam" },
    { pattern: /^(no class|class canceled|class cancelled)\b/, reason: "Class cancellation" }
  ];

  strongStarters.forEach(({ pattern, reason }) => {
    if (pattern.test(textLower)) {
      score += 3;
      reasons.push(`+3 ${reason}`);
    }
  });

  // === MEDIUM INDICATORS (+2 each) ===
  const mediumPatterns = [
    { pattern: /\boffice\s*hours?\b/, reason: "Office hours" },
    { pattern: /\d{1,2}:\d{2}\s*[-–to]+\s*\d{1,2}:\d{2}/, reason: "Time range" },
    { pattern: /\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?\s+\d/, reason: "Day + time" },
    { pattern: /\b(due|submit|by|before)\s*(:|on|by)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}\/)/, reason: "Due date" },
    { pattern: /\b\d+\s*(%|percent|points?)\b/, reason: "Grading info" },
    { pattern: /\b(grade|grading|evaluation|attendance|participation)\b/, reason: "Assessment term" },
    { pattern: /\b(on canvas|on blackboard|on moodle|on courseworks|course reserve)\b/, reason: "LMS reference" },
    { pattern: /\b(in person|in-person|zoom|virtual|hybrid)\b/, reason: "Meeting format" },
    { pattern: /\b(film screening|movie:|watch:|view:|listen to)\b/, reason: "Media instruction" },
    { pattern: /\b(response paper|reflection|blog post|discussion post|group project|presentation)\b/, reason: "Assignment type" }
  ];

  mediumPatterns.forEach(({ pattern, reason }) => {
    if (pattern.test(textLower)) {
      score += 2;
      reasons.push(`+2 ${reason}`);
    }
  });

  // === WEAK INDICATORS (+1 each) ===
  const weakPatterns = [
    { pattern: /\b(tba|tbd|to be announced|to be determined)\b/, reason: "TBA/TBD" },
    { pattern: /\b(see |refer to|check |visit )\b/, reason: "Reference directive" },
    { pattern: /\b(available on|available at|posted on)\b/, reason: "Availability info" },
    { pattern: /\b(professor |prof\.|prof |dr\.|dr |instructor:)\b/, reason: "Instructor reference" },
    { pattern: /\b(classroom|room |location:|class time|meeting time)\b/, reason: "Location/time info" },
    { pattern: /\b(this week|this class|today we|we will|we are)\b/, reason: "Class activity" },
    { pattern: /\b(in class|for class|before class|after class)\b/, reason: "Class context" }
  ];

  weakPatterns.forEach(({ pattern, reason }) => {
    if (pattern.test(textLower)) {
      score += 1;
      reasons.push(`+1 ${reason}`);
    }
  });

  // === NEGATIVE INDICATORS (suggest reading, not instruction) ===
  const negativePatterns = [
    { pattern: /^[A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)?\s*[\(,]\s*\d{4}/, reason: "Author (Year) format", penalty: -3 },
    { pattern: /\bpp?\.?\s*\d+[-–]?\d*/, reason: "Page numbers", penalty: -2 },
    { pattern: /\b(journal|quarterly|review|studies|proceedings)\s+of\b/, reason: "Academic journal", penalty: -2 },
    { pattern: /\b(university press|oxford|cambridge|routledge|sage|springer)\b/, reason: "Publisher name", penalty: -2 },
    { pattern: /\b(isbn|doi)\b|doi\.org/, reason: "Academic identifier", penalty: -2 }
  ];

  negativePatterns.forEach(({ pattern, reason, penalty }) => {
    if (pattern.test(textLower)) {
      score += penalty;
      reasons.push(`${penalty} ${reason}`);
    }
  });

  return { score, reasons };
}

/**
 * Check if text is an instruction (binary decision)
 * Returns true if score >= 3
 */
function isInstruction(text) {
  if (text.length < 15) return false;
  if (isHeader(text)) return false;

  const { score } = getInstructionScore(text);
  return score >= 3;
}

/**
 * Classify a paragraph and return classification with confidence
 * Returns: {type: string, confidence: number, reasons: string[]}
 *
 * Types: READING, HEADER, INSTRUCTION, UNCERTAIN, TOO_SHORT, OTHER
 */
function classifyParagraph(text) {
  text = text.trim();

  if (text.length < 20) {
    return { type: 'TOO_SHORT', confidence: 1.0, reasons: ['Text too short'] };
  }

  // Check header first (highest priority)
  if (isHeader(text)) {
    return { type: 'HEADER', confidence: 0.95, reasons: ['Detected as header'] };
  }

  // Check instruction
  if (isInstruction(text)) {
    const { score, reasons } = getInstructionScore(text);
    const confidence = Math.min(0.95, 0.6 + (score - 3) * 0.05);
    return { type: 'INSTRUCTION', confidence, reasons };
  }

  // Check reading
  const readingResult = getReadingScore(text);
  if (readingResult.score >= 3) {
    const confidence = Math.min(0.95, 0.6 + (readingResult.score - 3) * 0.05);
    return { type: 'READING', confidence, reasons: readingResult.reasons };
  }

  // Uncertain if score is 1-2 (some reading indicators but not enough)
  if (readingResult.score >= 1) {
    return {
      type: 'UNCERTAIN',
      confidence: 0.5,
      reasons: readingResult.reasons,
      readingScore: readingResult.score
    };
  }

  // Otherwise, classify as OTHER
  return { type: 'OTHER', confidence: 0.7, reasons: ['No strong indicators found'] };
}

/**
 * Extract week number from header text
 * Returns null if no week number found
 */
function extractWeekNumber(text) {
  const match = text.match(/week\s*(\d+)/i);
  return match ? parseInt(match[1]) : null;
}
