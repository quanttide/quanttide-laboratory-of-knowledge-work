"""判据：跑定义里写下的机械核对。

规则引擎的判据是**字段**，不是一行小语法：

  - executor: rule
    path: docs/index.md            # 路径存在
  - executor: rule
    absent: docs/old.md            # 路径不存在
  - executor: rule
    file: docs/index.md            # 文件含这段文字（file + contains 成对）
    contains: 第二大脑
  - executor: rule
    run: test -f docs/index.md     # 命令在工作区根跑，退出码为零

路径相对工作区根；写绝对路径则按绝对路径（跨仓库核对用）。
note 可省——省了由程序按字段拼一句；写就以写的为准。
"""

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

RULES = ("path", "absent", "file", "contains", "run")


@dataclass
class Item:
    """一条要跑的判据：说明 + 怎么判（kind 为空即不跑，交给智能体或人）。"""

    description: str
    kind: str | None = None
    args: tuple[str, ...] = field(default_factory=tuple)

    @property
    def machine(self) -> bool:
        return self.kind is not None

    def describe(self) -> str:
        if self.kind == "path":
            return f"存在：{self.args[0]}"
        if self.kind == "absent":
            return f"不存在：{self.args[0]}"
        if self.kind == "contains":
            return f"含「{self.args[1]}」：{self.args[0]}"
        if self.kind == "run":
            return f"跑通：{self.args[0]}"
        return ""


def description_of(criterion: dict) -> str:
    """说明：写了就用写的，没写按字段拼一句。"""
    written = str(criterion.get("description", "")).strip()
    if written:
        return written
    if "path" in criterion:
        return f"存在：{criterion['path']}"
    if "absent" in criterion:
        return f"不存在：{criterion['absent']}"
    if "file" in criterion:
        return f"含「{criterion['contains']}」：{criterion['file']}"
    if "run" in criterion:
        return f"跑通：{criterion['run']}"
    return ""


def items_of(criteria: list[dict]) -> list[Item]:
    """把定义里的判据翻成要跑的东西：rule 的跑，agent / human 的不跑。"""
    items: list[Item] = []
    for criterion in criteria:
        description = description_of(criterion)
        if criterion.get("executor") != "rule":
            items.append(Item(description))
            continue
        if "path" in criterion:
            items.append(Item(description, "path", (str(criterion["path"]).strip(),)))
        elif "absent" in criterion:
            items.append(Item(description, "absent", (str(criterion["absent"]).strip(),)))
        elif "file" in criterion:
            items.append(Item(description, "contains", (str(criterion["file"]).strip(), str(criterion["contains"]))))
        elif "run" in criterion:
            items.append(Item(description, "run", (str(criterion["run"]),)))
    return items


def check(root: Path, item: Item) -> tuple[bool, str]:
    """跑一条判据，返回（是否通过，说明）。"""
    kind, args = item.kind, item.args
    if kind == "path":
        return (root / args[0]).exists(), args[0]
    if kind == "absent":
        return not (root / args[0]).exists(), args[0]
    if kind == "contains":
        target, needle = args
        path = root / target
        if not path.is_file():
            return False, f"{target} 不存在"
        return needle in path.read_text(encoding="utf-8"), f"{target} 含「{needle}」"
    if kind == "run":
        done = subprocess.run(args[0], shell=True, cwd=root, capture_output=True, text=True)
        if done.returncode == 0:
            return True, args[0]
        tail = (done.stderr or done.stdout).strip().splitlines()
        return False, f"{args[0]}——{tail[-1] if tail else '无输出'}"
    return False, f"不认得的判据：{kind}"


def run(root: Path, items: list[Item]) -> tuple[list[tuple[Item, bool, str]], list[Item]]:
    """跑全部要跑的判据，返回（逐条结果，不跑的——留给智能体或人）。"""
    results = [(item, *check(root, item)) for item in items if item.machine]
    return results, [item for item in items if not item.machine]
