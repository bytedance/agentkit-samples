#!/usr/bin/env python3
"""第二步：复用工具模板，部署消费 SelfHosted 工具任务的 Dispatcher。"""

from _backend import main, run


if __name__ == "__main__":
    run(lambda: main(dispatcher=True))
