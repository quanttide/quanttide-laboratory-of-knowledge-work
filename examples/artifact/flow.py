"""日志分流：把日志内容转出到下游产物，上游仅留标题。

用法：
  python3 flow.py <日志文件> <目标文件>          交互选行转出
  python3 flow.py <日志文件> <目标文件> 1 3      按行号转出

规则（docs/handbook/artifacts/index.md）：
  - 标题行（#）不上游不下游，永远留在日志；
  - 转出即下游追加（下游组织自主，格式由下游规格约束）；
  - 转出后上游仅剩未选中内容，选空则仅留标题。
"""

import sys
from pathlib import Path


def selectable(lines):
    """可选转出的行：非空、非标题。"""
    return [(no, line) for no, line in enumerate(lines, 1) if line.strip() and not line.lstrip().startswith("#")]


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, dst = Path(argv[1]), Path(argv[2])
    lines = src.read_text(encoding="utf-8").splitlines()
    numbered = selectable(lines)

    if len(argv) > 3:
        picks = {int(n) for n in argv[3:]}
    else:
        for no, line in numbered:
            print(f"{no}: {line}")
        picks = {int(n) for n in input("转出行号（空格分隔）: ").split()}

    moving = [line for no, line in numbered if no in picks]
    if not moving:
        print("未选中任何可转出内容。")
        return 2

    with dst.open("a", encoding="utf-8") as f:
        f.write("\n".join(moving) + "\n")
    src.write_text("\n".join(line for no, line in enumerate(lines, 1) if no not in picks).strip() + "\n", encoding="utf-8")

    print(f"已转出 {len(moving)} 行 → {dst}")
    remaining = len(selectable(src.read_text(encoding="utf-8").splitlines()))
    print(f"上游剩余可转内容 {remaining} 行" + ("（仅留标题）" if remaining == 0 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
