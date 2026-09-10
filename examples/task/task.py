"""手册步骤封装：把 docs/handbook/tasks/*.md 解析为可加载、可校验的程序对象。

任务文件的三段式是机器可读契约：

    # 名称
    ## 目标    → goal: str
    ## 步骤    → steps: list[str]（有序列表，渲染器自动编号）
    ## 验收    → acceptance: list[str]（无序列表）

封装原则：本模块只读不抄——步骤的单一事实源在手册，改手册即改封装。

用法：
  python3 task.py list          列出全部已封装任务
  python3 task.py show <name>   展示一个任务的解析结果
  python3 task.py check         校验全部任务文件三段齐全
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Task:
    """一个手册任务：目标、步骤、验收。"""

    name: str
    goal: str = ""
    steps: list[str] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)

    def problems(self) -> list[str]:
        """验收封装本身：三段齐全且每段非空。"""
        missing = [part for part, value in
                   (("目标", self.goal), ("步骤", self.steps), ("验收", self.acceptance)) if not value]
        return [f"缺 {part}" for part in missing]


def handbook_dir(start: Path | None = None) -> Path:
    """向上查找 docs/handbook/tasks。"""
    d = (start or Path(__file__)).resolve().parent
    while not (d / "docs" / "handbook" / "tasks").is_dir():
        if d == d.parent:
            raise FileNotFoundError("未找到 docs/handbook/tasks")
        d = d.parent
    return d / "docs" / "handbook" / "tasks"


def parse(path: Path) -> Task:
    """解析一个任务文件；不合规的段落原样报缺，不做猜测。"""
    task, section = Task(name=path.stem), None
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text.startswith("## "):
            section = {"## 目标": "goal", "## 步骤": "steps", "## 流程": "steps", "## 验收": "acceptance"}.get(text)
        elif text.startswith("# ") and not task.goal and section is None:
            pass
        elif not text or section is None:
            continue
        elif section == "goal":
            task.goal += (" " if task.goal else "") + text
        elif text.startswith("- "):
            getattr(task, section).append(text[2:])
        elif text[0].isdigit() and ". " in text[:4]:
            getattr(task, section).append(text.split(". ", 1)[1])
    return task


def load_tasks() -> dict[str, Task]:
    return {p.stem: parse(p) for p in sorted(handbook_dir().glob("*.md"))}


def main(argv):
    tasks = load_tasks()
    if len(argv) < 2 or argv[1] == "list":
        for name, task in tasks.items():
            mark = "✓" if not task.problems() else "✗ " + "；".join(task.problems())
            print(f"{mark} {name}：{task.goal[:40]}…（{len(task.steps)} 步）")
        return 0
    if argv[1] == "check":
        bad = {n: t.problems() for n, t in tasks.items() if t.problems()}
        print("\n".join(f"{n}：{'；'.join(p)}" for n, p in bad.items()) or "全部任务三段齐全。")
        return 1 if bad else 0
    if argv[1] == "show" and len(argv) == 3:
        task = tasks.get(argv[2]) or (lambda: (_ for _ in ()).throw(SystemExit(f"无此任务：{argv[2]}")))()
        print(f"任务：{task.name}\n目标：{task.goal}\n步骤：")
        print("\n".join(f"  {i}. {s}" for i, s in enumerate(task.steps, 1)))
        print("验收：")
        print("\n".join(f"  - {a}" for a in task.acceptance))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
