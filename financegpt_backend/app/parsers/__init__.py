"""
Financial statement parsers for various institutions.
"""

from app.parsers.base_financial_parser import (
    AccountBalance,
    AccountType,
    BankTransaction,
    BaseFinancialParser,
    InvestmentHolding,
    InvestmentTransaction,
    TransactionType,
)
# from app.parsers.chase_parser import ChaseBankParser, ChaseCreditParser, ChaseParser
# from app.parsers.discover_parser import DiscoverParser
# from app.parsers.fidelity_parser import FidelityParser
from app.parsers.ofx_parser import OFXParser
from app.parsers.parser_factory import ParserFactory

__all__ = [
    # Base classes and data models
    "BaseFinancialParser",
    "BankTransaction",
    "InvestmentTransaction",
    "InvestmentHolding",
    "AccountBalance",
    "TransactionType",
    "AccountType",
    # Parsers
    # "ChaseParser",
    # "ChaseBankParser",
    # "ChaseCreditParser",
    # "FidelityParser",
    # "DiscoverParser",
    "OFXParser",
    # Factory
    "ParserFactory",
]

