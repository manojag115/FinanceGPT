"""
Bank of America connector using Plaid API.
"""

from app.tasks.plaid_indexers.plaid_base_indexer import PlaidBaseIndexer


class BankOfAmericaPlaidIndexer(PlaidBaseIndexer):
    """Bank of America connector powered by Plaid."""

    connector_name = "Bank of America"
    # For sandbox: use ins_109508 (First Platypus Bank - test institution)
    # For production: use ins_4 (Bank of America)
    institution_id = "ins_109508"
