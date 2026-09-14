"""python3 -m qtcloud_work 的入口。"""

import sys

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
