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
    ("qwen2.5-coder:7b", 4.7, 8, 16, "Medium", "Code assistance and completion; Qwen3 is preferred for autonomous tools", None, False),
    ("phi4:14b", 9.1, 16, 24, "Balanced", "Reasoning, math and technical chat; check native tool support", False, False),
]

# Variant pages are the source for download sizes and supported inputs.
# Capability is described by task, never inferred from weight or RAM size.
DETAILS = {
    "qwen3:14b": ("14B", 40960, "Q4_K_M", "Apache 2.0", "General agent", "Reasoning can increase response time."),
    "qwen3-coder:30b": ("30B total / 3B active", 262144, "Q4_K_M", "Apache 2.0", "Coding agent", "MoE activates fewer parameters but still needs memory for all weights."),
    "gpt-oss:20b": ("20B total / 3.6B active", 131072, "MXFP4", "Apache 2.0", "Reasoning agent", "MoE activates fewer parameters but still needs memory for all weights."),
    "llama3.3:70b": ("70B", 131072, "Q4_K_M", "Llama 3.3 Community License", "General agent", "Large weights require substantial memory; CPU use can be very slow."),
    "llama3.2:3b": ("3B", 131072, "Q4_K_M", "Llama 3.2 Community License", "Lightweight agent", "Small models are less reliable on complex multi-step tasks."),
    "mistral:7b": ("7B", 32768, "Q4_K_M", "Apache 2.0", "Lightweight agent", "Small models are less reliable on complex multi-step tasks."),
    "gemma3:12b": ("12B", 131072, "Q4_K_M", "Gemma Terms of Use", "Vision and chat", "No catalog native tool support: choose a tool-capable model for autonomous actions."),
    "deepseek-r1:14b": ("14B", 131072, "Q4_K_M", "MIT / base-model terms", "Reasoning and chat", "No catalog native tool support: choose a tool-capable model for autonomous actions."),
    "qwen2.5-coder:7b": ("7B", 32768, "Q4_K_M", "Apache 2.0", "Code assistance", "Native tool support depends on the installed variant; check engine metadata."),
    "phi4:14b": ("14B", 16384, "Q4_K_M", "MIT", "Reasoning and chat", "No catalog native tool support: choose a tool-capable model for autonomous actions."),
}
NOTE = "Hardware estimates include weight storage and basic overhead, not a benchmark. Long context needs extra memory. CPU-only use is supported but slower; GPU offloading is optional. Maximum context is the model limit, not this app's configured context."


def catalog():
    models = []
    for name, size, minimum, recommended, weight, uses, tools, vision in CATALOG:
        parameters, context, quantization, license_name, role, limitations = DETAILS[name]
        models.append({"name": name, "download_gb": size, "ram_min_gb": minimum, "ram_recommended_gb": recommended,
                       "vram_min_gb": round(size + 1), "vram_recommended_gb": round(size + 3), "weight": weight,
                       "capability": role, "uses": uses, "tools": tools, "vision": vision, "parameters": parameters,
                       "context_tokens": context, "quantization": quantization, "license": license_name,
                       "limitations": limitations, "metadata_origin": "Catalog estimates", "installed": False,
                       "source": "https://ollama.com/library/" + name, "checked": "2026-10-08", "note": NOTE})
    return models


def estimate(name, size_bytes=0):
    known = next((m for m in catalog() if m["name"] == name), None)
    if known:
        return known
    parameters = None  # A tag is not trustworthy evidence of architecture or parameter count.
    size = round(size_bytes / 1e9, 1) if size_bytes else None
    return {"name": name, "download_gb": size, "ram_min_gb": round(size + 4) if size else None,
            "ram_recommended_gb": round(size + 8) if size else None, "vram_min_gb": round(size + 1) if size else None, "vram_recommended_gb": round(size + 3) if size else None,
            "capability": "Unknown",
            "weight": "Unknown", "uses": "Consult the model's publisher and installed capabilities.", "tools": None, "vision": None,
            "parameters": parameters, "context_tokens": None, "quantization": None, "license": None,
            "metadata_origin": "Metadata unavailable", "installed": False,
            "source": "", "limitations": "Unverified model: task suitability and native tool support are unknown.", "note": NOTE}


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
