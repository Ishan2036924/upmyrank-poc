import logging
import time
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, doubt, feedback, health, mock, onboarding, session, student, study, taxonomy
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
    """v0.20.13 — measured-startup lifespan.

    Earlier attempt: split into phase-1 (blocking) + phase-2 (background)
    so /health could answer before the engine was ready. Reverted because
    5 endpoints (`/doubt/*`, `/session/end`, `/onboarding/submit`) grab
    `request.app.state.socratic_engine` synchronously — splitting required
    every call site to await an `engine_ready` event, ~30 LOC of plumbing.

    Net finding: Render free-tier cold-start is dominated by container
    provisioning (~15-30s), not Python boot (~3-5s). Optimising Python
    init from 5s → 2s saves the user 3 seconds out of a 30s cold start —
    not worth the regression risk. Instead we:
      - Drop the unnecessary `run_in_executor` wrap on `warm_up()` (it's
        a no-op log line for the OpenAI embedding service — the legacy
        sentence-transformers warm-up was retired in v0.7).
      - Time-stamp each step so future cold-start regressions are visible
        in Render logs without code changes.
    """
    logger.info("UpMyRank POC server is starting…")
    t0 = time.monotonic()

    await init_db()
    app.state.db_pool = get_pool()
    logger.info("[%dms] db pool ready", int((time.monotonic() - t0) * 1000))

    # No-op warm_up — OpenAI embeddings require no local model load.
    embed_svc = EmbeddingService()
    embed_svc.warm_up()
    logger.info("[%dms] embedding service ready", int((time.monotonic() - t0) * 1000))

    retriever = Retriever(db_pool=get_pool(), embedding_service=embed_svc)
    app.state.retriever = retriever

    openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    verifier = VerificationPipeline(
        sympy_checker=SymPyChecker(),
        llm_verifier=LLMVerifier(openai_client=openai_client),
    )
    app.state.verifier = verifier

    app.state.socratic_engine = SocraticEngine(
        openai_client=openai_client,
        retriever=retriever,
        db_pool=get_pool(),
        verifier=verifier,
    )
    logger.info(
        "[%dms] engine ready — model=%s; server live",
        int((time.monotonic() - t0) * 1000),
        settings.llm_model,
    )

    yield

    await close_db()
    logger.info("UpMyRank POC server shut down")


app = FastAPI(title="UpMyRank POC", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # Next.js dev
        "http://localhost:8501",        # Streamlit (legacy)
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8501",
        "https://upmyrank.vercel.app",  # production (update if custom domain)
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",  # all Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(admin.router)
app.include_router(doubt.router)
app.include_router(feedback.router)
app.include_router(session.router)
app.include_router(student.router)
app.include_router(mock.router)
app.include_router(study.router)
app.include_router(taxonomy.router)
