"""
Fidelity Investments connector using Plaid API.
"""

from app.tasks.plaid_indexers.plaid_base_indexer import PlaidBaseIndexer


class FidelityPlaidIndexer(PlaidBaseIndexer):
    """Fidelity Investments connector powered by Plaid."""

    connector_name = "Fidelity Investments"
    # For sandbox: use ins_109508 (First Platypus Bank - test institution)
    # For production: use ins_118051 (Fidelity)
    institution_id = "ins_109508"
