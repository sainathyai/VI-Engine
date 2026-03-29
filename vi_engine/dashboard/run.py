"""Launch the VI Engine review dashboard."""

import os

import uvicorn


def main() -> None:
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("DASHBOARD_PORT", "8501"))
    print(f"Starting VI Engine Dashboard at http://{host}:{port}")
    uvicorn.run(
        "vi_engine.dashboard.app:app",
        host=host,
        port=port,
        reload=True,
    )


if __name__ == "__main__":
    main()
