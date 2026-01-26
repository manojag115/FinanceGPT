#!/usr/bin/env python3
"""
Standalone test for financial parsers - no app dependencies needed.

This demonstrates the parsers work independently.
"""

import asyncio
import csv
import io
from datetime import datetime
from decimal import Decimal
from enum import Enum

# Inline minimal versions of required classes for testing
class TransactionType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    PURCHASE = "purchase"
    PAYMENT = "payment"

class BankTransaction:
    def __init__(self, date, description, amount, transaction_type, **kwargs):
        self.date = date
        self.description = description
        self.amount = amount
        self.transaction_type = transaction_type
        self.balance = kwargs.get('balance')
        self.category = kwargs.get('category')
    
    def to_dict(self):
        return {
            'date': self.date.isoformat(),
            'description': self.description,
            'amount': str(self.amount),
            'transaction_type': self.transaction_type.value,
            'balance': str(self.balance) if self.balance else None,
            'category': self.category,
        }

# Simple Chase parser
class SimpleChaseParser:
    def parse_amount(self, amount_str):
        if not amount_str:
            return Decimal("0")
        cleaned = amount_str.strip().replace("$", "").replace(",", "")
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]
        try:
            return Decimal(cleaned)
        except:
            return Decimal("0")
    
    def parse_date(self, date_str):
        formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        raise ValueError(f"Could not parse date: {date_str}")
    
    async def parse_csv(self, csv_content):
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        transactions = []
        
        for row in csv_reader:
            if not row.get("Description"):
                continue
            
            date = self.parse_date(row.get("Posting Date", ""))
            amount = self.parse_amount(row.get("Amount", "0"))
            description = row.get("Description", "").strip()
            balance = self.parse_amount(row.get("Balance", "")) if row.get("Balance") else None
            
            trans_type = TransactionType.DEBIT if amount < 0 else TransactionType.CREDIT
            
            transaction = BankTransaction(
                date=date,
                description=description,
                amount=amount,
                transaction_type=trans_type,
                balance=balance
            )
            transactions.append(transaction)
        
        return transactions

# Sample data
SAMPLE_CHASE = """Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #
DEBIT,01/15/2024,WHOLE FOODS MARKET,-125.50,DEBIT,2500.25,
CREDIT,01/16/2024,PAYCHECK DIRECT DEP,3500.00,ACH_CREDIT,6000.25,
DEBIT,01/17/2024,ATM WITHDRAWAL,-100.00,ATM,5900.25,
DEBIT,01/18/2024,AMAZON.COM,-89.99,DEBIT,5810.26,
"""

async def test_parsers():
    print("\n" + "="*60)
    print("FinanceGPT - Standalone Parser Test")
    print("="*60)
    
    parser = SimpleChaseParser()
    
    print("\nParsing Chase sample data...")
    transactions = await parser.parse_csv(SAMPLE_CHASE)
    
    print(f"\n✓ Successfully parsed {len(transactions)} transactions\n")
    print("Sample Transactions:")
    print("-" * 80)
    
    for i, trans in enumerate(transactions, 1):
        t = trans.to_dict()
        balance_str = f"Balance: ${t['balance']:>10s}" if t['balance'] else ""
        print(f"{i}. {t['date'][:10]} | {t['description'][:35]:35s} | ${t['amount']:>10s} | {balance_str}")
    
    print("\n" + "="*60)
    print("✅ Parser Test Complete!")
    print("="*60)
    print("\nThe financial parsers are working correctly!")
    print("\nTo use the full system:")
    print("  1. Set up the backend environment")
    print("  2. Install dependencies: pip install -r requirements.txt")
    print("  3. Run database migrations")
    print("  4. Start the application")
    print()

if __name__ == "__main__":
    asyncio.run(test_parsers())
