"""RasaAI environment diagnostic.

Run from the RasaAI project folder:
    python diagnose_environment.py

This script does not modify the environment or install packages.
It checks Python and imports used by the local video-analysis app.
"""

import importlib
import platform
import sys
import traceback

PACKAGES = [
    ("numpy", "NumPy"),
    ("cv2", "OpenCV"),
    ("mediapipe", "MediaPipe"),
    ("streamlit", "Streamlit"),
]

print("=" * 68)
print("RasaAI — Environment Diagnostic")
print("=" * 68)
print(f"Python executable : {sys.executable}")
print(f"Python version    : {sys.version.split()[0]}")
print(f"Operating system  : {platform.platform()}")
print()

failed = False
loaded = {}

for module_name, label in PACKAGES:
    print(f"[CHECK] {label} ({module_name})")
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "(version not exposed)")
        loaded[module_name] = module
        print(f"  PASS — version {version}")
    except Exception as exc:
        failed = True
        print(f"  FAIL — {type(exc).__name__}: {exc}")
        traceback.print_exc(limit=2)
    print()

if "numpy" in loaded and "cv2" in loaded:
    try:
        import numpy as np
        import cv2
        sample = np.zeros((32, 32, 3), dtype=np.uint8)
        gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
        print("[CHECK] NumPy + OpenCV basic operation")
        print(f"  {'PASS' if gray.shape == (32, 32) else 'FAIL'} — output shape {gray.shape}")
        if gray.shape != (32, 32):
            failed = True
    except Exception as exc:
        failed = True
        print(f"  FAIL — {type(exc).__name__}: {exc}")
    print()

if "mediapipe" in loaded:
    try:
        import mediapipe as mp
        has_pose = hasattr(getattr(mp, "solutions", None), "pose")
        print("[CHECK] MediaPipe Pose API")
        print(f"  {'PASS' if has_pose else 'FAIL'} — mp.solutions.pose available: {has_pose}")
        if not has_pose:
            print("  Note: the installed MediaPipe version may use a different API.")
            failed = True
    except Exception as exc:
        failed = True
        print(f"  FAIL — {type(exc).__name__}: {exc}")
    print()

print("=" * 68)
if failed:
    print("RESULT: One or more checks failed. Save this complete output and share it.")
    sys.exit(1)
print("RESULT: All diagnostic checks passed.")
print("Next: start Streamlit using this same Python environment.")
