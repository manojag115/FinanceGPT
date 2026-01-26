"""
FinanceGPT documentation search tool.

This tool allows the agent to search the pre-indexed FinanceGPT documentation
to help users with questions about how to use the application.

The documentation is indexed at deployment time from MDX files and stored
in dedicated tables (financegpt_docs_documents, financegpt_docs_chunks).
"""

import json

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import FinanceGPTDocsChunk, FinanceGPTDocsDocument


def format_financegpt_docs_results(results: list[tuple]) -> str:
    """
    Format search results into XML structure for the LLM context.

    Uses the same XML structure as format_documents_for_context from knowledge_base.py
    but with 'doc-' prefix on chunk IDs. This allows:
    - LLM to use consistent [citation:doc-XXX] format
    - Frontend to detect 'doc-' prefix and route to financegpt docs endpoint

    Args:
        results: List of (chunk, document) tuples from the database query

    Returns:
        Formatted XML string with documentation content and citation-ready chunks
    """
    if not results:
        return "No relevant FinanceGPT documentation found for your query."

    # Group chunks by document
    grouped: dict[int, dict] = {}
    for chunk, doc in results:
        if doc.id not in grouped:
            grouped[doc.id] = {
                "document_id": f"doc-{doc.id}",
                "document_type": "FINANCEGPT_DOCS",
                "title": doc.title,
                "url": doc.source,
                "metadata": {"source": doc.source},
                "chunks": [],
            }
        grouped[doc.id]["chunks"].append(
            {
                "chunk_id": f"doc-{chunk.id}",
                "content": chunk.content,
            }
        )

    # Render XML matching format_documents_for_context structure
    parts: list[str] = []
    for g in grouped.values():
        metadata_json = json.dumps(g["metadata"], ensure_ascii=False)

        parts.append("<document>")
        parts.append("<document_metadata>")
        parts.append(f"  <document_id>{g['document_id']}</document_id>")
        parts.append(f"  <document_type>{g['document_type']}</document_type>")
        parts.append(f"  <title><![CDATA[{g['title']}]]></title>")
        parts.append(f"  <url><![CDATA[{g['url']}]]></url>")
        parts.append(f"  <metadata_json><![CDATA[{metadata_json}]]></metadata_json>")
        parts.append("</document_metadata>")
        parts.append("")
        parts.append("<document_content>")

        for ch in g["chunks"]:
            parts.append(
                f"  <chunk id='{ch['chunk_id']}'><![CDATA[{ch['content']}]]></chunk>"
            )

        parts.append("</document_content>")
        parts.append("</document>")
        parts.append("")

    return "\n".join(parts).strip()


async def search_financegpt_docs_async(
    query: str,
    db_session: AsyncSession,
    top_k: int = 10,
) -> str:
    """
    Search FinanceGPT documentation using vector similarity.

    Args:
        query: The search query about FinanceGPT usage
        db_session: Database session for executing queries
        top_k: Number of results to return

    Returns:
        Formatted string with relevant documentation content
    """
    # Get embedding for the query
    query_embedding = config.embedding_model_instance.embed(query)

    # Vector similarity search on chunks, joining with documents
    stmt = (
        select(FinanceGPTDocsChunk, FinanceGPTDocsDocument)
        .join(
            FinanceGPTDocsDocument,
            FinanceGPTDocsChunk.document_id == FinanceGPTDocsDocument.id,
        )
        .order_by(FinanceGPTDocsChunk.embedding.op("<=>")(query_embedding))
        .limit(top_k)
    )

    result = await db_session.execute(stmt)
    rows = result.all()

    return format_financegpt_docs_results(rows)


def create_search_financegpt_docs_tool(db_session: AsyncSession):
    """
    Factory function to create the search_financegpt_docs tool.

    Args:
        db_session: Database session for executing queries

    Returns:
        A configured tool function for searching FinanceGPT documentation
    """

    @tool
    async def search_financegpt_docs(query: str, top_k: int = 10) -> str:
        """
        Search FinanceGPT documentation for help with using the application.

        Use this tool when the user asks questions about:
        - How to use FinanceGPT features
        - Installation and setup instructions
        - Configuration options and settings
        - Troubleshooting common issues
        - Available connectors and integrations
        - Browser extension usage
        - API documentation

        This searches the official FinanceGPT documentation that was indexed
        at deployment time. It does NOT search the user's personal knowledge base.

        Args:
            query: The search query about FinanceGPT usage or features
            top_k: Number of documentation chunks to retrieve (default: 10)

        Returns:
            Relevant documentation content formatted with chunk IDs for citations
        """
        return await search_financegpt_docs_async(
            query=query,
            db_session=db_session,
            top_k=top_k,
        )

    return search_financegpt_docs
