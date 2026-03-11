"""
CoCo Campus Kiosk - Entry Point
================================
Run with: python -m WEB_APP
"""
import uvicorn
from WEB_APP.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
