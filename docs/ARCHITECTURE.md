# Architecture

The browser calls a FastAPI application. Upload bytes are size-limited, never executed, and passed directly to format-specific extractors. A deterministic storyboard service maps explicit supported words into typed Pydantic scenes and reports unsupported content instead of silently substituting it.

The application Python environment does not import `bpy`. `blender_runner.py` discovers Blender and launches it with an explicit argument list and `shell=False`. Inside Blender, `scripts/fox_scene.py` creates reusable named objects, keyframes, lighting, camera motion, and output. Success requires a zero exit code and nonempty expected files.

Current rendering is procedural asset construction and animation—not generative text-to-3D AI. A future provider interface may add optional local language models without making them mandatory.
