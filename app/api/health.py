from fastapi import APIRouter

router = APIRouter()


# v0.20.13 — accept BOTH GET and HEAD on /health.
# UptimeRobot (and many other free uptime services) default to HEAD, which
# returned 405 Method Not Allowed and triggered false-positive "monitor down"
# alerts on 2026-04-29. HEAD is semantically valid for a health probe — body
# is irrelevant; only the status code matters.
@router.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "service": "upmyrank-poc"}
