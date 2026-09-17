"""Run the API:  python run.py  (or: uvicorn app.main:app --reload)"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)