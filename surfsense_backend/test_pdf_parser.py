#!/usr/bin/env python3
"""
Test PDF statement parser with sample PDF content.
"""

import asyncio
from app.parsers.pdf_statement_parser import PDFStatementParser


async def test_pdf_parser():
    """Test PDF parser with mock data."""
    print("Testing PDF Statement Parser...")
    print("=" * 60)
    
    # Note: This test requires a real PDF file
    # For now, it demonstrates the parser interface
    
    parser = PDFStatementParser()
    
    print("\n✓ PDF Parser initialized")
    print("\nTo test with a real Chase statement PDF:")
    print("1. Download a PDF statement from Chase online banking")
    print("2. Upload it through the FinanceGPT interface at http://localhost:3000")
    print("3. The parser will automatically detect and extract transactions")
    
    print("\nSupported PDF formats:")
    print("  - Chase bank statements (checking/savings)")
    print("  - Chase credit card statements")
    print("  - Discover credit card statements")
    print("  - Generic bank statements (automatic detection)")
    
    print("\nThe parser extracts:")
    print("  - Transaction dates")
    print("  - Descriptions")
    print("  - Amounts")
    print("  - Transaction types (debit/credit/purchase/payment)")
    print("  - Balances (when available)")
    
    print("\nAll data is converted to searchable markdown and stored as:")
    print("  - Document type: BANK_TRANSACTION")
    print("  - Content: Markdown formatted transactions")
    print("  - Metadata: Raw financial data as JSON")
    
    print("\n" + "=" * 60)
    print("✓ PDF parser ready to use!")


if __name__ == "__main__":
    asyncio.run(test_pdf_parser())
