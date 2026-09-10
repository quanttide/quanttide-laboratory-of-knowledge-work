"""判据：从指令的「验收」段里读机械核对，然后执行。

写法是一句说明加一个反引号给出的判据：

  机械：目标侧文件已就位 `path:docs/index.md`

判据四种——路径相对仓库根，写绝对路径则按绝对路径（跨仓库核对用）：

  path:<路径>          路径存在
  absent:<路径>        路径不存在
  contains:<路径>=<文字>  文件含这段文字
  run:<命令>           在仓库根跑该命令，退出码为 0

没有反引号判据的条目是闸门项，留给人拍板。
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ITEM = re.compile(r"^\s*-\s*\[[ xX]\]\s*(.+)$")
SPEC = re.compile(r"`([^`]+)`")


@dataclass
class Item:
    """一条检查项：说明 + 判据（判据为空即闸门项）。"""

    note: str
    spec: str | None = None

    @property
    def machine(self) -> bool:
        return self.spec is not None


def parse(text: str, section: str = "验收") -> list[Item]:
    """抽出某一节里的判据条目（任务的指令里，判据住在「验收」）。"""
    items: list[Item] = []
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == section
            continue
        if not inside:
            continue
        match = ITEM.match(line)
        if not match:
            continue
        body = match.group(1).strip()
        if "<" in body:  # 模板占位不算判据
            continue
        found = SPEC.search(body)
        items.append(Item(SPEC.sub("", body).strip(" ——：、"), found.group(1).strip() if found else None))
    return items


def check(root: Path, spec: str) -> tuple[bool, str]:
    """跑一条判据，返回（是否通过，说明）。"""
    if spec.startswith("path:"):
        return (root / spec[5:].strip()).exists(), spec
    if spec.startswith("absent:"):
        return not (root / spec[7:].strip()).exists(), spec
    if spec.startswith("contains:"):
        target, _, needle = spec[9:].partition("=")
        path = root / target.strip()
        if not path.is_file():
            return False, f"{target.strip()} 不存在"
        return needle in path.read_text(encoding="utf-8"), spec
    if spec.startswith("run:"):
        done = subprocess.run(spec[4:], shell=True, cwd=root, capture_output=True, text=True)
        if done.returncode == 0:
            return True, spec
        tail = (done.stderr or done.stdout).strip().splitlines()
        return False, f"{spec}——{tail[-1] if tail else '无输出'}"
    return False, f"无法识别的判据：{spec}"


def run(root: Path, items: list[Item]) -> tuple[list[tuple[Item, bool, str]], list[Item]]:
    """跑全部机械核对，返回（逐条结果，闸门项）。"""
    results = [(item, *check(root, item.spec)) for item in items if item.machine]
    return results, [item for item in items if not item.machine]
