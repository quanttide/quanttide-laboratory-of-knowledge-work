"""时刻：账本按发生顺序记，秒级够用。

单独一处，测试里可换掉（指向固定时刻）。
"""

from datetime import datetime

STAMP = "%Y-%m-%dT%H:%M:%S"


def now() -> str:
    return datetime.now().strftime(STAMP)
