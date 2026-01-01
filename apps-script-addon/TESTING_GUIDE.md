# Testing Guide - Google Workspace Add-on

Complete guide to deploy, test, and use the Syllabus Organizer add-on.

---

## 📋 Prerequisites

- ✅ Google account
- ✅ Google Chrome browser (recommended)
- ✅ Google Cloud Project with Drive & Docs APIs enabled

---

## 🚀 Step 1: Deploy the Add-on

### Option A: Manual Deployment (Recommended for Testing)

1. **Open Google Apps Script**:
   - Go to https://script.google.com
   - Click "+ New project"

2. **Copy the Code**:
   - For each `.gs` file in `apps-script-addon/`:
     - Click the `+` button next to "Files" in Apps Script editor
     - Choose "Script" for `.gs` files
     - Name it exactly as in the repository (e.g., `Classifier`, `PdfSearch`)
     - Copy and paste the entire content from GitHub

   - For each `.html` file:
     - Click the `+` button → "HTML"
     - Name it exactly (e.g., `Settings`, `Progress`, `Results`)
     - Copy and paste the content

   - Files to copy (in this order):
     1. `appsscript.json` (click ⚙️ icon → "Project Settings" → "Show 'appsscript.json'")
     2. `Code.gs`
     3. `Classifier.gs`
     4. `PdfSearch.gs`
     5. `DocumentProcessor.gs`
     6. `ProgressManager.gs`
     7. `Settings.gs`
     8. `Settings.html`
     9. `Progress.html`
     10. `Results.html`

3. **Save the Project**:
   - Click the disk icon or Ctrl+S
   - Name it "Syllabus Organizer"

### Option B: Using Clasp CLI (Advanced)

```bash
# Install clasp
npm install -g @google/clasp

# Login to Google
clasp login

# Navigate to add-on directory
cd apps-script-addon

# Create new Apps Script project
clasp create --type docs --title "Syllabus Organizer"

# Push code to Apps Script
clasp push

# Open in browser
clasp open
```

---

## 🧪 Step 2: Create a Test Google Doc

Create a test syllabus with various types of content to verify classification:

1. **Open Google Docs**: https://docs.google.com
2. **Create new document**: "Test Syllabus"
3. **Copy this sample content**:

```
Week 1: Introduction to Sociology

Required Readings:
Smith, John (2020). The Theory of Everything. New York: Oxford University Press, pp. 1-25.

Jones, Mary and Brown, David (2019). "Social Structures in Modern Society." Journal of Sociology, 45(2), 123-145.

Mills, C. Wright (1959). The Sociological Imagination. Oxford University Press. Chapter 1.

Optional:
Weber, Max (1905). The Protestant Ethic and the Spirit of Capitalism.

Week 2: Research Methods

Read Chapter 3 from the textbook by Friday.

Assignment: Submit your research proposal by October 15th.

Office hours: Mondays 2-4pm, Room 305

Please complete the reading before class on Thursday.

Week 3: Inequality

Recommended:
Piketty, Thomas (2014). Capital in the Twenty-First Century. Harvard University Press, pp. 50-100.

This course examines social inequality through various theoretical lenses. Students will learn how to analyze power structures in society.

What is inequality? How do we measure it?
```

4. **Save the document**

---

## ▶️ Step 3: Test the Add-on

### 3.1 Run in Test Mode

1. **In Apps Script Editor**:
   - Select `Code.gs` from files list
   - Find the `onOpen` function
   - Click "Run" button (▶️) at the top
   - **First time**: You'll get authorization prompt

2. **Grant Permissions**:
   - Click "Review Permissions"
   - Choose your Google account
   - Click "Advanced" → "Go to Syllabus Organizer (unsafe)"
   - Click "Allow"
   - ⚠️ **Note**: Shows "unsafe" because it's not verified yet - this is normal for development

3. **Refresh Your Test Doc**:
   - Go back to your test Google Doc
   - Refresh the page (F5 or Cmd+R)
   - You should see "Extensions" menu → "Syllabus Organizer"

### 3.2 Configure Settings

1. **Open Settings**:
   - Extensions → Syllabus Organizer → Configure Settings
   - Sidebar opens on the right

2. **Enter Your Information**:
   - **Email**: Your email (required for Unpaywall API)
   - **CORE API Key**: Leave blank for now (optional)
   - **Google NLP API Key**: Leave blank (optional)
   - Click "Save Settings"
   - Should see "Settings saved successfully!"

### 3.3 Process the Test Syllabus

1. **Start Processing**:
   - Extensions → Syllabus Organizer → Process Syllabus
   - Progress sidebar opens
   - Click "Start Processing"

2. **Watch the Progress**:
   - Progress bar updates in real-time
   - Statistics show:
     - Readings Found
     - PDFs Linked
     - Not Found
     - Uncertain Items

3. **Expected Results** for the sample content above:
   - **Readings Found**: ~5-6 (Smith 2020, Jones & Brown 2019, Mills 1959, Weber 1905, Piketty 2014)
   - **PDFs Linked**: ~2-4 (depending on availability)
   - **Not Found**: ~2-3 (some older works may not be in open access)
   - **Uncertain Items**: ~1-2 (borderline classifications)

4. **Check the Document**:
   - Linked readings should be **blue and underlined** (hyperlinks)
   - Click on a linked reading → Opens PDF in new tab
   - Non-linked readings remain black (PDF not found)

---

## 🔍 Step 4: Verify Classification Accuracy

### What Should Be Detected as Readings:

✅ **Correctly Classified**:
- `Smith, John (2020). The Theory of Everything...` → READING
- `Jones, Mary and Brown, David (2019). "Social Structures..."` → READING
- `Mills, C. Wright (1959). The Sociological Imagination.` → READING
- `Weber, Max (1905). The Protestant Ethic...` → READING
- `Piketty, Thomas (2014). Capital in the Twenty-First Century.` → READING

❌ **Should NOT Be Detected as Readings**:
- `Week 1: Introduction to Sociology` → HEADER
- `Read Chapter 3 from the textbook by Friday.` → INSTRUCTION
- `Assignment: Submit your research proposal...` → INSTRUCTION
- `Office hours: Mondays 2-4pm...` → INSTRUCTION
- `Please complete the reading before class...` → INSTRUCTION
- `This course examines social inequality...` → OTHER (course description)
- `What is inequality? How do we measure it?` → OTHER (question)

### View Uncertain Items:

1. **Extensions → Syllabus Organizer → View Progress**
2. Scroll down to "Uncertain Items" section
3. These are items with reading score between 1-2 (ambiguous)
4. Manually verify if they should be readings or not

---

## 🐛 Step 5: Debugging & Logs

### View Execution Logs:

1. **In Apps Script Editor**:
   - Click "Executions" (clock icon) on left sidebar
   - Shows all recent runs
   - Click on any execution to see detailed logs

2. **View Logger Output**:
   - View → Logs (Ctrl+Enter)
   - Shows all `Logger.log()` output
   - Useful for debugging PDF search

### Common Log Messages:

```
Searching for: Smith, John (2020). The Theory...
   Found DOI: 10.1234/example
   Found Unpaywall PDF: https://...
✓ Linked to: https://...

Searching for: Some Book (2000)...
   Trying Semantic Scholar...
   Trying CORE...
   Trying Open Library...
   No PDF found
✗ No PDF found
```

---

## 📊 Step 6: Measure Accuracy

Create a test syllabus with **known ground truth** and measure:

### Classification Accuracy:

```
Accuracy = Correct Classifications / Total Items

Example:
- 50 readings → 37 correctly detected = 74% accuracy ✅
- 10 headers → 10 correctly detected = 100% accuracy ✅
- 15 instructions → 12 correctly detected = 80% accuracy ✅
- Overall: (37+10+12) / (50+10+15) = 78.7% ✅
```

### PDF Link Success Rate:

```
Success Rate = PDFs Found / Total Readings

Example:
- 37 detected readings
- 18 PDFs found
- Success rate: 18/37 = 48.6% ✅ (within expected 40-60%)
```

---

## 🔄 Step 7: Test Continuation (Long Documents)

To test the 6-minute limit handling:

1. **Create a Large Test Doc**:
   - Copy 200+ reading citations
   - Mix with headers, instructions

2. **Start Processing**:
   - Watch for "Processing paused..." message
   - Should automatically resume after 1 minute
   - Progress persists between continuations

3. **Verify Progress Persistence**:
   - Extensions → Syllabus Organizer → Reset Progress
   - Start processing again
   - Should start from beginning

---

## 🎯 Step 8: Test Each PDF Source

Create test citations that specifically target each source:

### Unpaywall (Open Access Papers):
```
Piwowar, Heather and Priem, Jason (2018). "The State of OA: A large-scale analysis of the prevalence and impact of Open Access articles." PeerJ 6:e4375.
```

### Semantic Scholar:
```
LeCun, Yann, Bengio, Yoshua, and Hinton, Geoffrey (2015). "Deep learning." Nature 521.7553: 436-444.
```

### CORE:
```
Any UK university repository paper (e.g., from Oxford, Cambridge)
```

### Open Library (Books):
```
Orwell, George (1949). Nineteen Eighty-Four.
Austen, Jane (1813). Pride and Prejudice.
```

Add these to your test doc and verify each source works.

---

## ✅ Success Criteria

Your add-on is working correctly if:

- [x] Menu appears in Extensions after refresh
- [x] Settings save and load correctly
- [x] Progress sidebar shows real-time updates
- [x] Classification accuracy: 70-75% (within expected range)
- [x] PDF success rate: 40-60% (legal sources only)
- [x] Hyperlinks work (open PDFs in new tab)
- [x] Continuation works for long documents
- [x] No crashes or errors in execution logs
- [x] Uncertain items are flagged for review

---

## 🚨 Troubleshooting

### Issue: "Email not configured" error
**Solution**: Go to Settings and enter a valid email address

### Issue: No menu appears after refresh
**Solution**:
1. Check Apps Script project has `onOpen` function
2. Re-run authorization (Run → onOpen in Apps Script)
3. Hard refresh (Ctrl+Shift+R)

### Issue: "Script function not found: processDocument"
**Solution**: Make sure all `.gs` files are properly saved in Apps Script

### Issue: Very low PDF success rate (<20%)
**Solution**:
1. Check email is configured (Unpaywall needs it)
2. Try adding CORE API key (get free at core.ac.uk)
3. Verify test citations are valid (check DOIs exist)

### Issue: Progress stuck at 0%
**Solution**:
1. Check execution logs for errors
2. Verify settings are saved
3. Try "Reset Progress" and start again

### Issue: Authorization errors
**Solution**:
1. Apps Script → "Executions" → Clear failed runs
2. Re-authorize: Run → onOpen
3. Check OAuth scopes in appsscript.json

---

## 📈 Next Steps After Testing

Once testing is successful:

1. **Iterate on Accuracy**:
   - Collect false positives/negatives
   - Improve regex patterns in `Classifier.gs`
   - Test with real syllabi from professors

2. **Beta Testing**:
   - Share with 5-10 professors/students
   - Collect feedback via Google Form
   - Measure real-world accuracy

3. **Performance Optimization**:
   - Add more caching
   - Optimize API calls
   - Reduce execution time

4. **Marketplace Preparation**:
   - Create privacy policy
   - Create terms of service
   - Prepare screenshots and demo video
   - Submit for review

---

## 🎓 Advanced: Continuous Development

### Edit Code Locally:

```bash
# Pull latest from Apps Script
clasp pull

# Make changes to .gs files

# Push changes back
clasp push

# Test in Google Doc (refresh)
```

### Version Control:

```bash
# After making changes
git add -A
git commit -m "feat: Improve classification accuracy"
git push

# Deploy new version
clasp push
```

---

## 📞 Need Help?

- **GitHub Issues**: https://github.com/doreendai2005/syllabus-organizer/issues
- **Apps Script Docs**: https://developers.google.com/apps-script
- **Stack Overflow**: Tag `google-apps-script`

---

**Happy Testing! 🚀**
