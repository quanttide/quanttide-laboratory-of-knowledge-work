"""契约结构化验证：契约 = 目标 + 输出形态 + 必须包含的要素 + 检查项。

检查项分两类——机械核对（可写成断言，交给程序或 CI）与需人判断（留给闸门）。
样本是真实契约：从主体第二大脑向领域第二大脑迁移一份文档。

用法：
  python3 contract.py        打印契约并跑机械核对
"""

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# 契约层的文件名与本文件同名，按文件路径显式加载，避免撞车
_SPEC = importlib.util.spec_from_file_location(
    "resolver_contract", Path(__file__).resolve().parent.parent / "resolver" / "contract.py"
)
resolver_contract = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(resolver_contract)

repo_root = resolver_contract.repo_root


@dataclass
class Check:
    """一条检查项：说明 + 机械判定（无判定的交给闸门）。"""

    what: str
    test: Callable[[Path], bool] | None = None

    @property
    def machine(self) -> bool:
        return self.test is not None


@dataclass
class Contract:
    goal: str
    output: str
    must_include: list[str]
    checks: list[Check] = field(default_factory=list)

    def verify(self, root: Path) -> tuple[list[Check], list[Check]]:
        """跑机械核对，返回（通过的，未通过的）；需人判断的原样留出。"""
        passed, failed = [], []
        for check in (c for c in self.checks if c.machine):
            (passed if check.test(root) else failed).append(check)
        return passed, failed

    def gate(self) -> list[Check]:
        """留给闸门（人拍板）的检查项。"""
        return [c for c in self.checks if not c.machine]


# 真实契约：2026-09-10 把「Default 模块技术设计」从 quanttide-tech 迁入本领域
MIGRATION = Contract(
    goal="把主体第二大脑里属于本领域的文档迁入本领域",
    output="目标侧一份 Markdown 文档；源侧净缩短；逐层指针更新",
    must_include=["归属判定（它是哪件资产）", "落点（与源位置同构）", "来源（原位置）"],
    checks=[
        Check("目标侧文件已就位", lambda r: (r / "examples/default/docs/index.md").is_file()),
        Check("源侧文件已删除", lambda r: not (Path("/home/iguo/repos/quanttide/default/quanttide-tech") / "apps/qtdata/examples/default/modules/default.md").exists()),
        Check("落点与源位置同构（源在 examples/，目标也在实验室）"),
        Check("命名沿用目标侧规则（英文文件名、中文标题）"),
    ],
)


def main():
    root = repo_root()
    contract = MIGRATION
    print(f"契约：{contract.goal}\n")
    print(f"输出形态：{contract.output}")
    print("必须包含的要素：" + "；".join(contract.must_include) + "\n")

    passed, failed = contract.verify(root)
    print("机械核对：")
    for check in passed:
        print(f"  ✓ {check.what}")
    for check in failed:
        print(f"  ✗ {check.what}")
    print("需人判断（留给闸门）：")
    for check in contract.gate():
        print(f"  - {check.what}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
