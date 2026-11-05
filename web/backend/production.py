"""Serve the built SPA and real API on one loopback origin (no internet needed)."""
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from .app import app, ROOT

DIST = ROOT / "web/frontend/dist"


@app.get("/{spa_path:path}", include_in_schema=False)
def frontend(spa_path: str):
    candidate = (DIST / spa_path).resolve()
    if not candidate.is_relative_to(DIST.resolve()):
        raise HTTPException(404, "资源不存在")
    if candidate.is_file():
        return FileResponse(candidate)
    if spa_path.startswith("api/") or Path(spa_path).suffix:
        raise HTTPException(404, "资源不存在")
    index = DIST / "index.html"
    if not index.is_file():
        raise HTTPException(503, "请先在 web/frontend 运行 npm run build")
    return FileResponse(index)
