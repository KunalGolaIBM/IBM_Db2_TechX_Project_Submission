"""Server entrypoint for Db2 WorkRelay Intelligence."""
import os
import uvicorn
from app.api import app

def run():
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run()
