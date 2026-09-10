"""Validation benchmarks: bundled reference data to verify the toolchain."""

from fastapi import APIRouter, HTTPException

from app.services.benchmark import get_benchmark, list_benchmarks

router = APIRouter()


@router.get("/")
async def benchmarks():
    return list_benchmarks()


@router.get("/{benchmark_id}")
async def benchmark(benchmark_id: str):
    b = get_benchmark(benchmark_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return b
