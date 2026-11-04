#!/usr/bin/env python3
"""第一步：创建工具 Sandbox 模板，保存供 Dispatcher 使用的 ToolId。"""

from _backend import main, run


if __name__ == "__main__":
    run(lambda: main(dispatcher=False))
