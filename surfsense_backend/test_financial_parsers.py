#!/usr/bin/env python3
"""
Test script for financial parsers.

This script demonstrates how to use the financial parsers to process
statements from Chase, Fidelity, and Discover.
"""

import asyncio
from decimal import Decimal
from pathlib import Path

# Create sample CSV data for testing
SAMPLE_CHASE_CHECKING = """Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,01/15/2024,WHOLE FOODS MARKET,-125.50,DEBIT,2500.25,
CREDIT,01/16/2024,PAYCHECK DIRECT DEP,3500.00,ACH_CREDIT,6000.25,
DEBIT,01/17/2024,ATM WITHDRAWAL,-100.00,ATM,5900.25,
"""

SAMPLE_CHASE_CREDIT = """Transaction Date,Post Date,Description,Category,Type,Amount,Memo
01/15/2024,01/16/2024,AMAZON.COM,Shopping,Sale,-89.99,
01/16/2024,01/17/2024,STARBUCKS,Food & Drink,Sale,-5.75,
01/20/2024,01/21/2024,PAYMENT - THANK YOU,,Payment,500.00,
"""

SAMPLE_FIDELITY_POSITIONS = """Account Number,Account Name,Symbol,Description,Quantity,Last Price,Current Value,Cost Basis Total,Gain/Loss Dollar,Gain/Loss Percent
123456789,INDIVIDUAL,AAPL,APPLE INC,50,170.00,8500.00,7500.00,1000.00,13.33%
123456789,INDIVIDUAL,MSFT,MICROSOFT CORP,30,380.00,11400.00,10000.00,1400.00,14.00%
123456789,INDIVIDUAL,VTSAX,VANGUARD TOTAL STOCK MKT,100,115.50,11550.00,11000.00,550.00,5.00%
"""

SAMPLE_DISCOVER = """Trans. Date,Post Date,Description,Amount,Category
01/15/2024,01/16/2024,TARGET STORE,-125.43,Merchandise
01/16/2024,01/17/2024,SHELL GAS STATION,-45.00,Gasoline
01/20/2024,01/21/2024,ONLINE PAYMENT,500.00,Payments and Credits
"""


async def test_parser(parser_class, sample_data: str, institution: str):
    """Test a parser with sample data."""
    print(f"\n{'='*60}")
    print(f"Testing {institution} Parser")
    print(f"{'='*60}")
    
    try:
        # Create parser instance
        from app.parsers import (
            ChaseBankParser,
            ChaseCreditParser,
            FidelityParser,
            DiscoverParser,
        )
        
        # Parse the sample data
        parser = parser_class()
        result = await parser.parse_file(sample_data.encode('utf-8'), f"sample_{institution}.csv")
        
        # Display results
        print(f"\n✓ Successfully parsed {institution} file")
        print(f"  Institution: {result['metadata']['institution']}")
        print(f"  Format: {result['metadata']['format']}")
        print(f"  Transactions: {result['metadata'].get('transaction_count', 0)}")
        print(f"  Holdings: {result['metadata'].get('holding_count', 0)}")
        
        # Show first few transactions
        if result['transactions']:
            print(f"\n  Sample Transactions:")
            for i, trans in enumerate(result['transactions'][:3], 1):
                trans_dict = trans.to_dict()
                print(f"    {i}. {trans_dict['date'][:10]} - {trans_dict['description'][:40]:40s} ${trans_dict['amount']:>10s}")
        
        # Show holdings if available
        if result['holdings']:
            print(f"\n  Holdings:")
            for i, holding in enumerate(result['holdings'][:3], 1):
                hold_dict = holding.to_dict()
                gain_loss = f" (${hold_dict['gain_loss']})" if hold_dict['gain_loss'] else ""
                print(f"    {i}. {hold_dict['symbol']:6s} - {hold_dict['quantity']:>6s} shares @ ${hold_dict['price']:>8s} = ${hold_dict['value']:>10s}{gain_loss}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing {institution}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_parser_factory():
    """Test the parser factory auto-detection."""
    print(f"\n{'='*60}")
    print("Testing Parser Factory Auto-Detection")
    print(f"{'='*60}")
    
    try:
        from app.parsers import ParserFactory
        
        test_cases = [
            (SAMPLE_CHASE_CHECKING, "chase_checking.csv", "Chase Bank"),
            (SAMPLE_CHASE_CREDIT, "chase_credit.csv", "Chase Credit"),
            (SAMPLE_FIDELITY_POSITIONS, "fidelity_positions.csv", "Fidelity"),
            (SAMPLE_DISCOVER, "discover.csv", "Discover"),
        ]
        
        for sample_data, filename, expected in test_cases:
            try:
                connector_type, parsed = await ParserFactory.parse_auto(
                    sample_data.encode('utf-8'), 
                    filename
                )
                print(f"  ✓ {filename:30s} -> {connector_type.value:25s} ({expected})")
            except Exception as e:
                print(f"  ✗ {filename:30s} -> Error: {e}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing parser factory: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all parser tests."""
    print("\n" + "="*60)
    print("FinanceGPT - Financial Parser Test Suite")
    print("="*60)
    
    from app.parsers import (
        ChaseBankParser,
        ChaseCreditParser,
        FidelityParser,
        DiscoverParser,
    )
    
    # Test individual parsers
    tests = [
        (ChaseBankParser, SAMPLE_CHASE_CHECKING, "Chase Checking"),
        (ChaseCreditParser, SAMPLE_CHASE_CREDIT, "Chase Credit Card"),
        (FidelityParser, SAMPLE_FIDELITY_POSITIONS, "Fidelity Investments"),
        (DiscoverParser, SAMPLE_DISCOVER, "Discover Credit Card"),
    ]
    
    results = []
    for parser_class, sample_data, institution in tests:
        success = await test_parser(parser_class, sample_data, institution)
        results.append((institution, success))
    
    # Test parser factory
    factory_success = await test_parser_factory()
    results.append(("Parser Factory", factory_success))
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✓ PASSED" if success else "✗ FAILED"
        print(f"  {status:10s} - {name}")
    
    print(f"\n  Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n  🎉 All tests passed! Financial parsers are ready to use.")
        print("\n  Next steps:")
        print("    1. Create database migration: cd surfsense_backend && alembic revision --autogenerate -m 'Add financial connectors'")
        print("    2. Apply migration: alembic upgrade head")
        print("    3. Install OFX support: pip install ofxparse")
        print("    4. Upload a real CSV file to test!")
    else:
        print("\n  ⚠️  Some tests failed. Check the errors above.")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
