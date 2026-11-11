"""
CivicConnect – Frontend API Client Extension
Patches the existing React app's classify endpoint to point at the
FastAPI backend (IBM Db2 + LangChain) instead of the legacy Node.js server.

This file shows the minimal diff needed to wire the React frontend
to the new Python backend. Drop it next to the existing server.ts.
"""

# This is a documentation file — see server integration notes in README.md.
# The React frontend calls /api/ai/classify and /api/complaints.
# Change the Vite proxy target in vite.config.ts to point to the FastAPI server:
#
#   // vite.config.ts
#   server: {
#     proxy: {
#       '/api': 'http://localhost:8000'   // FastAPI backend
#     }
#   }
#
# No changes are required in the React component code itself.
