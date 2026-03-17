import asyncio
import logging
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import doubt, health, mock, session, student
from app.config import settings
from app.db.database import close_db, get_pool, init_db
from app.services.doubt.engine import SocraticEngine
from app.services.rag.embeddings import EmbeddingService
from app.services.rag.retriever import Retriever
from app.services.verify import LLMVerifier, SymPyChecker, VerificationPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("UpMyRank POC server is starting…")

    # ── 1. Database pool ──────────────────────────────────────────────────────
    await init_db()
    app.state.db_pool = get_pool()          # expose pool directly on app.state

    # ── 2. Embedding service (model load is CPU-bound → thread executor) ──────
    embed_svc = EmbeddingService()
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, embed_svc.warm_up)

    # ── 3. Retriever ──────────────────────────────────────────────────────────
    retriever = Retriever(db_pool=get_pool(), embedding_service=embed_svc)
    app.state.retriever = retriever
    logger.info("Retriever initialised")

    # ── 4. OpenAI client ─────────────────────────────────────────────────────
    openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # ── 5. Verification pipeline ──────────────────────────────────────────────
    verifier = VerificationPipeline(
        sympy_checker=SymPyChecker(),
        llm_verifier=LLMVerifier(openai_client=openai_client),
    )
    app.state.verifier = verifier
    logger.info("VerificationPipeline initialised")

    # ── 6. Socratic engine ────────────────────────────────────────────────────
    app.state.socratic_engine = SocraticEngine(
        openai_client=openai_client,
        retriever=retriever,
        db_pool=get_pool(),
        verifier=verifier,
    )
    logger.info("SocraticEngine initialised (model=%s)", settings.llm_model)

    logger.info("UpMyRank POC server is running")
    yield

    # ── shutdown ──────────────────────────────────────────────────────────────
    await close_db()
    logger.info("UpMyRank POC server shut down")


app = FastAPI(title="UpMyRank POC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:8501",   # Streamlit (backward compat)
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(doubt.router)
app.include_router(session.router)
app.include_router(student.router)
app.include_router(mock.router)
