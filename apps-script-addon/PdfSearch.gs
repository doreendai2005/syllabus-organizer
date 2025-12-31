/**
 * PDF Search Module
 * Searches legal open-access sources for academic PDFs
 *
 * Legal sources: Crossref, Unpaywall, Semantic Scholar, CORE, Open Library
 * Ported from organizer.py lines 984-1274 (legal sources only)
 */

// API Endpoints
const CROSSREF_API = 'https://api.crossref.org/works';
const UNPAYWALL_API = 'https://api.unpaywall.org/v2';
const SEMANTIC_SCHOLAR_API = 'https://api.semanticscholar.org/graph/v1';
const CORE_API = 'https://api.core.ac.uk/v3';
const OPEN_LIBRARY_API = 'https://openlibrary.org';

/**
 * Clean citation for search - remove page numbers, years, volume info
 * Ported from organizer.py lines 953-958
 */
function cleanQuery(text) {
  let clean = text;
  clean = clean.replace(/pp?\.?\s*\d+[-–]?\d*/g, '');   // Remove page numbers
  clean = clean.replace(/\(\d{4}\)/g, '');              // Remove years in parens
  clean = clean.replace(/vol\.?\s*\d+/gi, '');          // Remove volume
  clean = clean.trim().replace(/\s+/g, ' ');            // Normalize whitespace
  return clean.substring(0, 150);                       // Limit length
}

/**
 * Find DOI via Crossref API
 * Ported from organizer.py lines 984-996
 */
function findDoi(text) {
  try {
    const query = encodeURIComponent(cleanQuery(text));
    const url = `${CROSSREF_API}?query=${query}&rows=1`;

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      if (data.message && data.message.items && data.message.items.length > 0) {
        const doi = data.message.items[0].DOI;
        if (doi) {
          Logger.log(`   Found DOI: ${doi}`);
          return doi;
        }
      }
    }
  } catch (e) {
    Logger.log(`   Crossref error: ${e}`);
  }

  return null;
}

/**
 * Search Unpaywall for open access PDF
 * Ported from organizer.py lines 1069-1083
 * Requires email parameter for API access
 */
function searchUnpaywall(doi, email) {
  if (!email) return null;

  try {
    const url = `${UNPAYWALL_API}/${doi}?email=${encodeURIComponent(email)}`;

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      if (data.is_oa && data.best_oa_location) {
        const pdfUrl = data.best_oa_location.url_for_pdf;
        if (pdfUrl) {
          Logger.log(`   Found Unpaywall PDF: ${pdfUrl.substring(0, 50)}...`);
          return pdfUrl;
        }
      }
    }
  } catch (e) {
    Logger.log(`   Unpaywall error: ${e}`);
  }

  return null;
}

/**
 * Search Semantic Scholar for open access PDF
 * Ported from organizer.py lines 1086-1120
 * Can search by DOI or by query text
 */
function searchSemanticScholar(query, doi) {
  Logger.log('   Trying Semantic Scholar...');

  try {
    let url;
    const headers = { 'User-Agent': 'Mozilla/5.0' };

    // If we have a DOI, search by DOI directly
    if (doi) {
      url = `${SEMANTIC_SCHOLAR_API}/paper/DOI:${doi}?fields=openAccessPdf,isOpenAccess`;

      const response = UrlFetchApp.fetch(url, {
        muteHttpExceptions: true,
        headers: headers
      });

      if (response.getResponseCode() === 200) {
        const data = JSON.parse(response.getContentText());
        if (data.isOpenAccess && data.openAccessPdf) {
          const pdfUrl = data.openAccessPdf.url;
          if (pdfUrl) {
            Logger.log('   Found Semantic Scholar PDF!');
            return pdfUrl;
          }
        }
      }
    }

    // Fallback to title search
    const cleanedQuery = encodeURIComponent(cleanQuery(query));
    url = `${SEMANTIC_SCHOLAR_API}/paper/search?query=${cleanedQuery}&limit=3&fields=openAccessPdf,isOpenAccess,title`;

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: headers
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      if (data.data && data.data.length > 0) {
        for (const paper of data.data) {
          if (paper.isOpenAccess && paper.openAccessPdf) {
            const pdfUrl = paper.openAccessPdf.url;
            if (pdfUrl) {
              Logger.log('   Found Semantic Scholar PDF!');
              return pdfUrl;
            }
          }
        }
      }
    }
  } catch (e) {
    Logger.log(`   Semantic Scholar error: ${e}`);
  }

  return null;
}

/**
 * Search CORE for open access PDF
 * Ported from organizer.py lines 1123-1153
 * Optional API key can be provided via settings
 */
function searchCore(query, doi) {
  Logger.log('   Trying CORE...');

  try {
    const settings = loadSettings();
    const headers = { 'User-Agent': 'Mozilla/5.0' };

    // Add API key if available
    if (settings.coreApiKey) {
      headers['Authorization'] = `Bearer ${settings.coreApiKey}`;
    }

    const searchTerm = doi || cleanQuery(query);
    const url = `${CORE_API}/search/works?q=${encodeURIComponent(searchTerm)}&limit=5`;

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: headers
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      const results = data.results || [];

      for (const result of results) {
        // Check for downloadUrl
        if (result.downloadUrl && result.downloadUrl.endsWith('.pdf')) {
          Logger.log('   Found CORE PDF!');
          return result.downloadUrl;
        }

        // Check links array
        if (result.links) {
          for (const link of result.links) {
            if (link.type === 'download' || (link.url && link.url.includes('.pdf'))) {
              Logger.log('   Found CORE PDF!');
              return link.url;
            }
          }
        }
      }
    }
  } catch (e) {
    Logger.log(`   CORE error: ${e}`);
  }

  return null;
}

/**
 * Search Open Library and Internet Archive for books
 * Ported from organizer.py lines 1219-1274
 * Returns PDF URL from Internet Archive if available
 */
function searchOpenLibrary(query) {
  Logger.log('   Trying Open Library...');

  try {
    const searchTerm = encodeURIComponent(cleanQuery(query));
    const url = `${OPEN_LIBRARY_API}/search.json?q=${searchTerm}&limit=5`;

    const response = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: { 'User-Agent': 'Mozilla/5.0' }
    });

    if (response.getResponseCode() !== 200) {
      return null;
    }

    const data = JSON.parse(response.getContentText());
    const docs = data.docs || [];

    for (const doc of docs) {
      // Check if book has readable version
      if (doc.has_fulltext || doc.public_scan_b) {
        // Try direct Internet Archive link if available
        if (doc.ia && doc.ia.length > 0) {
          const iaId = doc.ia[0];
          const pdfUrl = `https://archive.org/download/${iaId}/${iaId}.pdf`;

          // Quick check if PDF exists (HEAD request)
          try {
            const headResponse = UrlFetchApp.fetch(pdfUrl, {
              method: 'head',
              muteHttpExceptions: true
            });

            if (headResponse.getResponseCode() === 200) {
              Logger.log('   Found Open Library/Archive.org PDF!');
              return pdfUrl;
            }
          } catch (e) {
            // Continue to next result
          }
        }

        // Try Read API for downloadable version
        let editionKey = null;
        if (doc.edition_key && doc.edition_key.length > 0) {
          editionKey = doc.edition_key[0];
        } else if (doc.cover_edition_key) {
          editionKey = doc.cover_edition_key;
        }

        if (editionKey) {
          try {
            const readUrl = `${OPEN_LIBRARY_API}/api/volumes/brief/olid/${editionKey}.json`;
            const readResponse = UrlFetchApp.fetch(readUrl, {
              muteHttpExceptions: true,
              headers: { 'User-Agent': 'Mozilla/5.0' }
            });

            if (readResponse.getResponseCode() === 200) {
              const readData = JSON.parse(readResponse.getContentText());
              const records = readData.records || {};

              for (const recordKey in records) {
                const record = records[recordKey];
                if (record.data && record.data.items) {
                  for (const item of record.data.items) {
                    if (item.status === 'full access') {
                      const itemUrl = item.itemURL || '';
                      const iaId = itemUrl.split('/').pop();
                      if (iaId) {
                        const pdfUrl = `https://archive.org/download/${iaId}/${iaId}.pdf`;
                        Logger.log('   Found Open Library PDF!');
                        return pdfUrl;
                      }
                    }
                  }
                }
              }
            }
          } catch (e) {
            // Continue to next result
          }
        }
      }
    }
  } catch (e) {
    Logger.log(`   Open Library error: ${e}`);
  }

  return null;
}

/**
 * Find PDF for a reading citation
 * Orchestrates search across all legal sources
 * Ported from organizer.py lines 1586-1679 (legal sources only)
 *
 * Search order:
 *   Papers (if DOI found): Crossref -> Unpaywall -> Semantic Scholar -> CORE
 *   Books (no DOI or papers failed): Open Library -> Semantic Scholar -> CORE
 *
 * Returns: PDF URL or null if not found
 */
function findPdf(text, email) {
  Logger.log(`Searching for: ${text.substring(0, 80)}...`);

  // Step 1: Try to find DOI via Crossref
  const doi = findDoi(text);

  if (doi) {
    Logger.log('   Academic paper detected (DOI found)');

    // Step 2: Try Unpaywall (legal OA)
    if (email) {
      const unpaywallUrl = searchUnpaywall(doi, email);
      if (unpaywallUrl) return unpaywallUrl;
    }

    // Step 3: Try Semantic Scholar
    const semanticUrl = searchSemanticScholar(text, doi);
    if (semanticUrl) return semanticUrl;

    // Step 4: Try CORE
    const coreUrl = searchCore(text, doi);
    if (coreUrl) return coreUrl;
  }

  // Book sources (no DOI or paper sources failed)
  Logger.log('   Trying book sources...');

  // Step 5: Try Open Library / Internet Archive
  const openLibUrl = searchOpenLibrary(text);
  if (openLibUrl) return openLibUrl;

  // Step 6: Try Semantic Scholar without DOI (fallback)
  const semanticUrl2 = searchSemanticScholar(text, null);
  if (semanticUrl2) return semanticUrl2;

  // Step 7: Try CORE without DOI (fallback)
  const coreUrl2 = searchCore(text, null);
  if (coreUrl2) return coreUrl2;

  // No PDF found
  Logger.log('   No PDF found');
  return null;
}

/**
 * Find PDF with caching to reduce API calls
 * Uses CacheService to cache results for 6 hours
 */
function findPdfCached(text, email) {
  const cache = CacheService.getDocumentCache();
  const cacheKey = 'pdf_' + Utilities.computeDigest(
    Utilities.DigestAlgorithm.MD5,
    text,
    Utilities.Charset.UTF_8
  ).map(byte => (byte < 0 ? byte + 256 : byte).toString(16).padStart(2, '0')).join('');

  // Check cache
  const cached = cache.get(cacheKey);
  if (cached !== null) {
    Logger.log(`Cache hit for: ${text.substring(0, 50)}...`);
    return cached === 'NULL' ? null : cached;
  }

  // Search for PDF
  const result = findPdf(text, email);

  // Cache result (6 hours = 21600 seconds)
  cache.put(cacheKey, result || 'NULL', 21600);

  return result;
}
