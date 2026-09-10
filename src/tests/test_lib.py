#!/usr/bin/env python3
"""最小测试：不用额外依赖，干净检出上直接跑。

  python3 src/tests/test_lib.py

两套夹具：一套是真实仓库（集成，会因为仓库变脏而报红），
一套是临时目录里现搭的假仓库（单元，不碰任何真文件）。
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "resolver"))
sys.path.insert(0, str(HERE.parent / "kit"))
import catalog as catalog_layer  # noqa: E402
import checks as checks_layer  # noqa: E402
import contract as contract_layer  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def test(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def fake_repo(tmp: Path, stray: bool = False) -> Path:
    """按契约搭一个齐备的假仓库，可选塞一个未登记目录。"""
    root = tmp / "second-brain"
    for asset in contract_layer.assets():
        if asset.name in contract_layer.LOCATION:
            continue
        (root / ("data" if asset.name in {n for _, n in contract_layer.STATED} else "docs") / asset.name).mkdir(parents=True)
    (root / "packages" / "quanttide-demo-toolkit").mkdir(parents=True)
    (root / "apps" / "demo").mkdir(parents=True)
    (root / "examples" / "default").mkdir(parents=True)
    if stray:
        (root / "data" / "未登记目录").mkdir(parents=True)
    return root


def main() -> int:
    real = contract_layer.repo_root()

    test("契约是二十格", len(contract_layer.assets()) == 20, f"实得 {len(contract_layer.assets())}")
    test("真实仓库二十格齐备", not contract_layer.missing(real), f"缺 {[a.kind for a in contract_layer.missing(real)]}")

    with tempfile.TemporaryDirectory() as tmp:
        clean = fake_repo(Path(tmp) / "clean")
        test("假仓库：齐备时无缺资产", not contract_layer.missing(clean))
        test("假仓库：齐备时无未登记", not catalog_layer.build(clean).unregistered(clean))
        dirty = fake_repo(Path(tmp) / "dirty", stray=True)
        stray = catalog_layer.build(dirty).unregistered(dirty)
        test("假仓库：未登记目录被揪出", [p.name for p in stray] == ["未登记目录"], f"实得 {[p.name for p in stray]}")

    catalog = catalog_layer.build(real)
    hits = catalog.find("材料")
    test("按名词条命中规格", any("material.md" in str(e.path) for e in hits), f"实得 {[str(e.path) for e in hits]}")
    test("模糊兜底命中", bool(catalog.find("日志规范")), "「日志规范」应能落到日志相关条目")

    contract_text = """## 检查项

- [ ] 机械：目标侧文件已就位 `path:quanttide-demo-toolkit`
- [ ] 机械：旧文件已删除 `absent:gone.md`
- [ ] 机械：读了说明书 `contains:说明.md=第二大脑`
- [ ] 机械：命令跑得通 `run:test -f 说明.md`
- [ ] 闸门：落点与源位置同构
"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "repo"
        root.mkdir()
        (root / "quanttide-demo-toolkit").mkdir()
        (root / "说明.md").write_text("这是量潮第二大脑的说明。\n", encoding="utf-8")
        items = checks_layer.parse(contract_text)
        results, gates = checks_layer.run(root, items)
        test("检查项：机械与闸门分得开", len(results) == 4 and len(gates) == 1, f"机械 {len(results)}，闸门 {len(gates)}")
        test("检查项：四条机械项全通过与判据无关的排版", all(ok for _, ok, _ in results), "；".join(f"{d}→{ok}" for _, ok, d in results))
        (root / "gone.md").write_text("还在\n", encoding="utf-8")
        failed = [ok for _, ok, _ in checks_layer.run(root, items)[0]]
        test("检查项：判据不该通过时会报红", failed.count(False) == 1, f"实得 {failed}")

    for name, ok, detail in RESULTS:
        print(f"{'✓' if ok else '✗'} {name}" + (f"——{detail}" if detail and not ok else ""))
    bad = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} 通过。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
