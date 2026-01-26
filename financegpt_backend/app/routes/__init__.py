from fastapi import APIRouter

from .chat_comments_routes import router as chat_comments_router
from .composio_routes import router as composio_router
from .documents_routes import router as documents_router
from .editor_routes import router as editor_router
from .logs_routes import router as logs_router
from .new_chat_routes import router as new_chat_router
from .new_llm_config_routes import router as new_llm_config_router
from .notes_routes import router as notes_router
from .notifications_routes import router as notifications_router
from .plaid_routes import router as plaid_router
from .rbac_routes import router as rbac_router
from .search_source_connectors_routes import router as search_source_connectors_router
from .search_spaces_routes import router as search_spaces_router
from .financegpt_docs_routes import router as financegpt_docs_router

router = APIRouter()

router.include_router(search_spaces_router)
router.include_router(rbac_router)  # RBAC routes for roles, members, invites
router.include_router(editor_router)
router.include_router(documents_router)
router.include_router(notes_router)
router.include_router(new_chat_router)  # Chat with assistant-ui persistence
router.include_router(chat_comments_router)
router.include_router(search_source_connectors_router)
router.include_router(plaid_router)  # Plaid bank connectors
router.include_router(new_llm_config_router)  # LLM configs with prompt configuration
router.include_router(logs_router)
router.include_router(financegpt_docs_router)  # FinanceGPT documentation for citations
router.include_router(notifications_router)  # Notifications with Electric SQL sync
router.include_router(composio_router)  # Composio OAuth and toolkit management
