from __future__ import annotations

import argparse
import os
import sys
import uvicorn

# 1. 显式导入 app 对象，这样 PyInstaller 就能追踪到依赖
# 同时避免了 uvicorn 运行时动态寻找模块失败的问题
from app.main import app 

def main() -> None:
    # 兼容打包环境的路径搜索逻辑
    if getattr(sys, 'frozen', False):
        curr_path = os.path.dirname(sys.executable)
        if curr_path not in sys.path:
            sys.path.insert(0, curr_path)

    parser = argparse.ArgumentParser(description="WriterBook sidecar executable entry")
    parser.add_argument("--host", default=os.getenv("ENGINE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", os.getenv("ENGINE_PORT", "17777"))))
    args = parser.parse_args()
    
    # 2. 直接传入对象 app，而不是字符串 "app.main:app"
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main() # 这里应该调用上面的 main 函数，而不是手动再写一遍 run