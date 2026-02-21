from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="WriterBook sidecar executable entry")
    parser.add_argument("--host", default=os.getenv("ENGINE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", os.getenv("ENGINE_PORT", "17777"))))
    args = parser.parse_args()
    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()

