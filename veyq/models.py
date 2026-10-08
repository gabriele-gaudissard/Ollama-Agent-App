"""Curated local model catalog; hardware figures are estimates, not guarantees."""
import ctypes
import os
import re
import shutil

CATALOG = [
    ("qwen3:14b", 9.3, 16, 24, "Balanced", "Agent tasks, coding, reasoning and multilingual work", True, False),
    ("qwen3-coder:30b", 19, 32, 48, "Heavy", "Repository work, code generation and tool-driven development", True, False),
    ("gpt-oss:20b", 14, 20, 32, "Heavy", "Agent workflows, reasoning and developer tasks", True, False),
    ("llama3.3:70b", 43, 64, 96, "Very heavy", "Advanced general writing, multilingual analysis and tools", True, False),
    ("llama3.2:3b", 2, 6, 8, "Light", "Fast chat, summarization and simple tools on smaller PCs", True, False),
    ("mistral:7b", 4.4, 8, 16, "Medium", "General writing, analysis and lightweight tool tasks", True, False),
    ("gemma3:12b", 8.1, 16, 24, "Balanced", "Image understanding, document discussion and general chat; check tool support", False, True),
    ("deepseek-r1:14b", 9, 16, 24, "Balanced", "Math, reasoning and analysis; native tool support varies", False, False),
    ("qwen2.5-coder:7b", 4.7, 8, 16, "Medium", "Code assistance and completion; Qwen3 is preferred for autonomous tools", False, False),
    ("phi4:14b", 9.1, 16, 24, "Balanced", "Reasoning, math and technical chat; check native tool support", False, False),
]


def catalog():
    return [{"name": name, "download_gb": size, "ram_min_gb": minimum, "ram_recommended_gb": recommended,
             "vram_min_gb": round(size + 1), "vram_recommended_gb": round(size + 3), "weight": weight,
             "capability": "Advanced" if minimum >= 20 else "General purpose" if minimum >= 12 else "Entry level", "uses": uses, "tools": tools, "vision": vision,
             "source": "https://ollama.com/library/" + name.split(":")[0], "checked": "2026-10-08",
             "note": "Approximate default quantized sizes. RAM includes operating-system overhead; context, quantization and offloading change requirements. CPU-only use works but can be slow. VRAM is optional when using RAM/CPU. Catalog is curated, not a popularity ranking."}
            for name, size, minimum, recommended, weight, uses, tools, vision in CATALOG]


def estimate(name, size_bytes=0):
    known = next((m for m in catalog() if m["name"] == name), None)
    if known:
        return known
    match = re.search(r"(?:^|[:_-])(\d+(?:\.\d+)?)b(?:$|[-_])", name, re.I)
    parameters = float(match[1]) if match else None
    size = round(size_bytes / 1e9, 1) if size_bytes else round(parameters * .65, 1) if parameters else None
    return {"name": name, "download_gb": size, "ram_min_gb": round(size + 4) if size else None,
            "ram_recommended_gb": round(size + 8) if size else None, "vram_min_gb": round(size + 1) if size else None, "vram_recommended_gb": round(size + 3) if size else None,
            "capability": "Unknown",
            "weight": "Estimated", "uses": "Consult the model's publisher and installed capabilities.", "tools": None, "vision": None,
            "source": "", "note": "Unknown model: rough Q4-weight estimate from parameter count, or actual installed size. Quantization, context and architecture can make this inaccurate. Not a hardware guarantee."}


def hardware(workspace):
    ram = None
    if os.name == "nt":
        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), *[(n, ctypes.c_ulonglong) for n in ("total", "available", "page", "avail_page", "virtual", "avail_virtual", "extended")]]
        status = Memory()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            ram = round(status.total / 1024 ** 3, 1)
    free = shutil.disk_usage(workspace).free / 1e9
    return {"ram_gb": ram, "disk_free_gb": round(free, 1), "note": "RAM and disk are detected locally. GPU memory is not inferred from RAM; partial GPU offloading is supported by the selected engine."}
