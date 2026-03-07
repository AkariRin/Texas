"""Development entry point — run with: python main.py"""

import uvicorn

from src.core.config import Settings

if __name__ == "__main__":
    settings = Settings()
    uvicorn.run(
        "src.core.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["src"],
    )

