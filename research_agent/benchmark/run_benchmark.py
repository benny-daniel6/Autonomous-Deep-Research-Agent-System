"""
Benchmark runner for the research agent pipeline.

Runs 50 queries sequentially, logs results to a CSV, and prints a summary.
"""

import asyncio
import csv
import logging
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from research_agent.benchmark.test_queries import BENCHMARK_QUERIES
from research_agent.graph.graph_builder import research_graph
from research_agent.memory.chroma_store import get_memory_store

# Set logging level to warning to keep console output clean during benchmark
logging.getLogger("research_agent").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def run_single_query(category: str, query: str) -> dict[str, Any]:
    """Run a single query through the graph and extract metrics."""
    start_time = time.perf_counter()
    
    try:
        final_state = await research_graph.ainvoke({"query": query})
        latency = time.perf_counter() - start_time
        
        report = final_state.get("final_report")
        error_log = final_state.get("error_log", [])
        memory_hits = final_state.get("memory_hits", [])
        critique = final_state.get("critique")
        retry_count = final_state.get("retry_count", 0)
        
        # A task is completed if it produced a report with quality_score > 0
        quality_score = report.quality_score if report else 0.0
        task_completion = quality_score > 0.0
        
        return {
            "category": category,
            "query": query,
            "task_completion": task_completion,
            "latency_seconds": round(latency, 2),
            "retry_count": retry_count,
            "memory_hit": len(memory_hits) > 0,
            "quality_score": quality_score,
            "critic_verdict": critique.verdict if critique else "N/A",
            "error_count": len(error_log)
        }
    except Exception as e:
        latency = time.perf_counter() - start_time
        logger.error(f"Catastrophic failure on query '{query}': {e}")
        return {
            "category": category,
            "query": query,
            "task_completion": False,
            "latency_seconds": round(latency, 2),
            "retry_count": 0,
            "memory_hit": False,
            "quality_score": 0.0,
            "critic_verdict": "ERROR",
            "error_count": 1
        }


async def run_benchmark():
    load_dotenv()
    
    # Optionally clear memory before benchmark to test full pipeline execution
    # get_memory_store().clear()
    
    results = []
    
    print(f"Starting benchmark for {len(BENCHMARK_QUERIES)} queries...")
    print("-" * 50)
    
    for i, (category, query) in enumerate(BENCHMARK_QUERIES, 1):
        print(f"[{i}/{len(BENCHMARK_QUERIES)}] {category}: {query}")
        result = await run_single_query(category, query)
        results.append(result)
        
        status = "✅ PASS" if result["task_completion"] else "❌ FAIL"
        print(f"  -> {status} | Latency: {result['latency_seconds']}s | Quality: {result['quality_score']:.2f} | Errors: {result['error_count']}")
        
    print("-" * 50)
    
    # Save to CSV
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    csv_path = results_dir / "benchmark_results.csv"
    
    keys = results[0].keys()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)
        
    print(f"\nResults saved to {csv_path}")
    
    # Print Summary
    total = len(results)
    completed = sum(1 for r in results if r["task_completion"])
    completion_rate = (completed / total) * 100
    
    avg_latency = sum(r["latency_seconds"] for r in results) / total
    avg_quality = sum(r["quality_score"] for r in results) / total
    
    memory_hits = sum(1 for r in results if r["memory_hit"])
    memory_hit_rate = (memory_hits / total) * 100
    
    print("\n" + "=" * 50)
    print("BENCHMARK SUMMARY")
    print("=" * 50)
    print(f"Completion Rate:   {completion_rate:.1f}% ({completed}/{total})")
    print(f"Avg Latency:       {avg_latency:.1f}s")
    print(f"Avg Quality Score: {avg_quality:.2f}")
    print(f"Memory Hit Rate:   {memory_hit_rate:.1f}%")
    
    print("\nFailure Breakdown by Category:")
    failures = [r for r in results if not r["task_completion"]]
    if not failures:
        print("  No failures!")
    else:
        fail_counts = {}
        for f in failures:
            fail_counts[f["category"]] = fail_counts.get(f["category"], 0) + 1
        for cat, count in fail_counts.items():
            print(f"  - {cat}: {count} failure(s)")
            
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())
