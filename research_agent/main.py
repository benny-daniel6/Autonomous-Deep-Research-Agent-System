"""
FastAPI application for the Multi-Agent Research System.

Provides endpoints to trigger research queries and check health/benchmark results.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from research_agent.graph.graph_builder import research_graph
from research_agent.memory.chroma_store import get_memory_store
from research_agent.models.schemas import Report

# Load environment variables (API keys)
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Multi-Agent Research API",
    description="API for the Autonomous Deep Research Agent System",
    version="1.0.0",
)

# Allow CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    query: str = Field(..., description="The research query.")
    stream: bool = Field(False, description="Whether to stream updates (not currently fully implemented).")


@app.post("/research", response_model=Report)
async def run_research(req: ResearchRequest) -> Any:
    """Execute a research query through the LangGraph pipeline."""
    logger.info("Received research request for query: '%s'", req.query)
    try:
        # The LangGraph ainvoke method expects the initial state dict
        final_state = await research_graph.ainvoke({"query": req.query})
        
        report = final_state.get("final_report")
        if not report:
            raise HTTPException(status_code=500, detail="Pipeline finished without producing a report.")
        
        return report
    except Exception as e:
        logger.exception("Error running research pipeline: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Check API health and memory store status."""
    try:
        store = get_memory_store()
        memory_count = store.count
        return {"status": "ok", "memory_count": memory_count}
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return {"status": "error", "detail": str(e)}


@app.get("/benchmark/results")
async def get_benchmark_results() -> list[dict[str, Any]]:
    """Return the benchmark results CSV data as JSON."""
    results_path = Path(__file__).parent / "benchmark" / "results" / "benchmark_results.csv"
    if not results_path.exists():
        return []

    try:
        import pandas as pd
        df = pd.read_csv(results_path)
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error("Failed to read benchmark results: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read benchmark results.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("research_agent.main:app", host="0.0.0.0", port=8000, reload=True)
