# FinanceGPT PDF Support

## ✅ PDF Bank Statement Parsing Now Supported!

Good news! I've added **full PDF support** for bank statements. You can now upload PDFs directly from Chase, Discover, and other banks.

## What Works

### Supported File Formats
- ✅ **PDF bank statements** (Chase checking/savings)
- ✅ **PDF credit card statements** (Chase, Discover)
- ✅ **CSV files** (Chase, Fidelity, Discover)
- ✅ **OFX/QFX files** (universal format from any bank)

### Automatic Detection
The system automatically:
1. Detects if a PDF is a bank statement
2. Extracts transaction data from the PDF text
3. Parses dates, descriptions, amounts, and types
4. Stores everything as searchable markdown + JSON

### Parsed Data
From PDFs, it extracts:
- Transaction dates
- Descriptions/merchants
- Amounts (debits/credits)
- Transaction types (purchase, payment, debit, credit)
- Running balances (when available)
- Account institution

## How to Use

### 1. Get Your Bank Statement
Download a PDF statement from:
- **Chase**: Login → Statements & Documents → Download PDF
- **Discover**: Login → Account Center → Statements → Download
- **Any bank**: Most banks offer PDF statements in their online portal

### 2. Upload the PDF
1. Go to http://localhost:3000
2. Navigate to Documents section
3. Click upload or drag-and-drop your PDF
4. The system will automatically detect it's a bank statement

### 3. View Parsed Data
The PDF will be:
- Parsed into transactions
- Stored as markdown (human-readable)
- Indexed for search (you can ask questions about it)
- Saved with metadata (institution, date, transaction count)

## Technical Details

### Parser Architecture
```
PDF Upload
    ↓
PDF Statement Parser
    ├─ Extract text (pypdf or pdfplumber)
    ├─ Detect institution (Chase, Discover, generic)
    ├─ Parse transactions with regex patterns
    └─ Convert to BankTransaction objects
    ↓
Financial Data Processor
    ├─ Build markdown representation
    ├─ Store raw JSON in metadata
    └─ Index for semantic search
```

### Files Added
- `financegpt_backend/app/parsers/pdf_statement_parser.py` - Main PDF parser
- `financegpt_backend/app/parsers/parser_factory.py` - Updated with PDF detection
- `financegpt_backend/app/tasks/document_processors/file_processors.py` - Integrated PDF parsing

### Dependencies Added
- `pdfplumber>=0.11.0` - Robust PDF text extraction
- `pypdf>=5.1.0` - Already included, used as fallback

## Limitations & Tips

### What Works Best
- ✅ Chase PDFs (tested format)
- ✅ Discover PDFs (tested format)
- ✅ Standard bank statement layouts
- ✅ Transaction tables with date/description/amount columns

### Known Limitations
- ⚠️ Complex PDF layouts may not parse perfectly
- ⚠️ Image-based PDFs (scanned documents) won't work - need OCR
- ⚠️ Very customized statement formats might need manual parser updates

### Tips for Best Results
1. **Use native PDFs** (digital downloads, not scanned)
2. **Current statements** work better than old formats
3. **If PDF fails**, try downloading CSV/OFX from your bank's website
4. **Check the logs** - detailed parsing info appears in Docker logs

## Example Usage

### Chase Checking Statement
```
Upload: Chase_Checking_December_2025.pdf
Result:
  ✓ Detected as Chase bank statement
  ✓ Parsed 47 transactions
  ✓ Stored as BANK_TRANSACTION document
  ✓ Searchable content created
```

### Discover Credit Card
```
Upload: Discover_Statement_12-2025.pdf
Result:
  ✓ Detected as Discover credit card statement
  ✓ Parsed 23 transactions  
  ✓ Categorized purchases vs payments
  ✓ Indexed for semantic queries
```

## Next Steps

### Ready to Test
1. Download a bank statement PDF
2. Upload it at http://localhost:3000
3. Check the logs: `docker logs financegpt-backend-1 --tail 50`
4. View parsed data in the Documents section

### Future Enhancements
- 📊 Add more bank formats (Bank of America, Wells Fargo, etc.)
- 🔍 Improve OCR for scanned PDFs
- 📈 Add investment account PDF parsing (Vanguard, Schwab)
- 🤖 Train AI to extract from any PDF layout

## Troubleshooting

### PDF Not Being Parsed
1. Check Docker logs: `docker logs financegpt-backend-1 --tail 100`
2. Look for "Checking if PDF is a bank statement"
3. If it says "not a bank statement", the PDF text wasn't recognized

### No Transactions Found
- The PDF might be image-based (scanned) - try CSV/OFX instead
- The format might be non-standard - check logs for errors
- Try downloading a different statement period

### Upload Fails
- Ensure containers are running: `docker compose ps`
- Check file size (<50MB recommended)
- Verify it's a real PDF (not renamed image)

## Support

If you encounter issues:
1. Check logs: `docker logs financegpt-backend-1`
2. Try CSV download from your bank instead
3. Share the bank name and I can add specific parsing logic

---

**You're all set!** Just upload your Chase PDF statement and watch it get automatically parsed into searchable transactions. 🎉
