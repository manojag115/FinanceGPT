"""
Chase Bank connector using Plaid API.
"""

from app.tasks.plaid_indexers.plaid_base_indexer import PlaidBaseIndexer


class ChasePlaidIndexer(PlaidBaseIndexer):
    """Chase Bank connector powered by Plaid."""

    connector_name = "Chase Bank"
    # For sandbox: use ins_109508 (First Platypus Bank - test institution)
    # For production: use ins_3 (Chase)
    institution_id = "ins_109508"
