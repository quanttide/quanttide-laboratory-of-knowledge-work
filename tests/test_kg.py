#!/usr/bin/env python3
"""程序自带测试：不用额外依赖，干净检出上直接跑。

  python3 tests/test_kg.py

两套夹具：真实工作区（集成，仓库变脏就报红）与临时目录里现搭的假仓库（单元，不碰真文件）。
"""

import json
import os
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB / "src"))

from kg import assets as assets_layer  # noqa: E402
from kg import catalog as catalog_layer  # noqa: E402
from kg import checks as checks_layer  # noqa: E402
from kg import cli, material as material_layer  # noqa: E402
from kg import records  # noqa: E402
from kg import report  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def test(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def fake_repo(tmp: Path, stray: bool = False) -> Path:
    """按契约搭一个齐备的假仓库，可选塞一个未登记目录。"""
    root = tmp / "second-brain"
    stated = {name for _, name in assets_layer.STATED}
    for asset in assets_layer.assets():
        if asset.name in assets_layer.LOCATION:
            continue
        (root / ("data" if asset.name in stated else "docs") / asset.name).mkdir(parents=True)
    (root / "packages" / "quanttide-demo-toolkit").mkdir(parents=True)
    (root / "apps" / "demo").mkdir(parents=True)
    (root / "examples" / "default").mkdir(parents=True)
    if stray:
        (root / "data" / "未登记目录").mkdir(parents=True)
    return root


def with_repo(root: Path) -> None:
    """给假仓库装上 git 并提交一次，让材料的时间字段有处可取。"""
    import subprocess

    for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.email=lab@example.com", "-c", "user.name=lab", "commit", "-qm", "首次提交"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "--amend", "--date=2026-09-10T09:00:00", "--no-edit"], cwd=root, check=True, capture_output=True)


def case_file(path: Path, material: str = "", contract: str = "", output: str = "") -> Path:
    """写一份一件事的文件，哪一段要填就填。"""
    body = ["# 一件事：试一条路", ""]
    for name, item in (("材料", material), ("契约", contract), ("产出", output), ("案卷", "")):
        body += [f"## {name}", ""]
        if item:
            body.append(f"- `{item}`")
        body.append("")
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def links(real: Path) -> None:
    """动作之间的四条链接：立契约、写案卷、补格子、串成一件事。"""
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp) / "案卷.md"
        result = report.audit_contract(real, LAB / "samples" / "migration.md", into=dossier)
        text = dossier.read_text(encoding="utf-8") if dossier.is_file() else ""
        test("链接①：核对契约把审查者报告写进案卷", result.ok and "## 审查者报告" in text and "✓ 机械：目标侧文件已就位" in text)
        test("链接①：写出来的案卷自查通过", report.audit_dossier(dossier).ok)

        target = Path(tmp) / "契约.md"
        report.new_contract(target, "data/journal/README.md")
        fresh = target.read_text(encoding="utf-8")
        test("链接③：以某件东西为题立契约", "改 `data/journal/README.md`" in fresh and "来源：`data/journal/README.md`" in fresh)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "second-brain"
        (root / "data" / "journal").mkdir(parents=True)
        before = len(assets_layer.missing(root))
        report.audit(root, make=True)
        left = {asset.name for asset in assets_layer.missing(root)}
        test("链接②：审计能补建缺的格子", len(assets_layer.missing(root)) < before and (root / "data" / "history" / "README.md").is_file())
        test("链接②：独立仓库那三格不凭空建", left == set(assets_layer.LOCATION), f"剩 {sorted(left)}")

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "case")  # 用假仓库当工作区，引用都相对它
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 今天\n", encoding="utf-8")
        (root / "契约.md").write_text("# 契约\n", encoding="utf-8")
        (root / "产出.md").write_text("# 产出\n", encoding="utf-8")
        one = case_file(Path(tmp) / "一件事.md")
        test("主轴：空的一件事指向第一步", "先记材料" in report.case(root, one).lines[-1])
        case_file(one, material="data/journal/2026-09-10.md")
        test("主轴：有材料就指向立契约", "new-contract" in report.case(root, one).lines[-1])
        case_file(one, material="data/journal/2026-09-10.md", contract="契约.md", output="产出.md")
        test("主轴：有契约有产出就指向写案卷", "--into" in report.case(root, one).lines[-1])
        case_file(one, material="data/不存在.md")
        broken = report.case(root, one)
        test("主轴：断链点得出来", not broken.ok and "断链" in "".join(broken.lines))


def gui_smoke(real: Path) -> None:
    """界面冒烟：装了 PySide6 的窗口模块就跑，没装就跳过（不影响其它项）。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication

        from kg import gui
    except ImportError:
        print("（未装 PySide6 窗口模块，跳过界面冒烟：pip install PySide6-Essentials）")
        return
    app = QApplication.instance() or QApplication([])
    window = gui.Window(real)
    window.select_action("目录")
    test("界面：目录出得了表", bool(window.run_current().rows))
    window.select_action("审计")
    test("界面：审计通过", window.run_current().ok)
    window.select_action("核对契约")
    window.widgets["契约文件"].setText(str(LAB / "samples" / "migration.md"))
    audit = window.run_current()
    test("界面：核对真实契约", audit.ok and len(audit.rows) >= 4, f"行 {len(audit.rows)}")
    window.select_action("目录")
    window.run_current()
    window.table.setCurrentCell(0, 1)
    test("界面：选中一行能取到路径", bool(window._selected_path()), window._selected_path())
    window.select_action("找文档")
    test("界面：空输入先拦住", not window.run_current().ok)
    groups = [spec.group for spec in gui.SPECS]
    test("界面：动作分五组", groups == ["一件事", "一件事", "工作区", "工作区", "查看", "查看", "契约", "契约", "案卷", "案卷"], str(groups))
    window.close()
    del app


def main() -> int:
    real = assets_layer.repo_root()

    test("契约是二十格", len(assets_layer.assets()) == 20, f"实得 {len(assets_layer.assets())}")
    test("真实工作区二十格齐备", not assets_layer.missing(real), f"缺 {[a.kind for a in assets_layer.missing(real)]}")

    with tempfile.TemporaryDirectory() as tmp:
        clean = fake_repo(Path(tmp) / "clean")
        test("假仓库：齐备时无缺资产", not assets_layer.missing(clean))
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
        test("检查项：四条机械核对全通过", all(ok for _, ok, _ in results), "；".join(f"{d}→{ok}" for _, ok, d in results))
        (root / "gone.md").write_text("还在\n", encoding="utf-8")
        failed = [ok for _, ok, _ in checks_layer.run(root, items)[0]]
        test("检查项：该报红时报红", failed.count(False) == 1, f"实得 {failed}")

    test("记录的段位取自同一处", records.CONTRACT_SECTIONS == ("目标", "输出形态", "必须包含", "检查项"), "契约四段")
    test("案卷段位是四段", len(records.DOSSIER_SECTIONS) == 4, "产出 / 审查 / 裁决 / 成果")

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "materials")
        (root / "data" / "journal" / "2026-09-10.md").write_text("# 二〇二六年九月十日\n\n今天把程序收成一个。\n", encoding="utf-8")
        (root / "data" / "profile" / "iGuo.md").write_text("# 我\n\n档案一页。\n", encoding="utf-8")
        with_repo(root)  # 提交一次，时间才取得到首次提交日期
        found = dict(material_layer.materials(root))
        by_rel = {rel: mat for rel, mat in found.items()}
        journal = by_rel["data/journal/2026-09-10.md"]
        profile = by_rel["data/profile/iGuo.md"]
        test("材料：四字段填得出", not journal.missing and not profile.missing, f"缺 {journal.missing + profile.missing}")
        test("材料：时间退回文件名里的日期", journal.created_at == "2026-09-10", f"实得 {journal.created_at}")
        test("材料：阶段由位置承担", journal.stage == "原始" and profile.stage == "材料", f"{journal.stage}/{profile.stage}")

    links(real)

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_repo(Path(tmp) / "cli")
        out = Path(tmp) / "报告.json"
        code = cli.main(["--root", str(root), "audit", "--json", str(out)])
        report = json.loads(out.read_text(encoding="utf-8"))
        test("命令行：审计齐备返回零", code == 0 and report["result"] == "通过", f"exit={code}")
        code = cli.main(["--root", str(root), "find", "不存在的名字"])
        test("命令行：找不到返回非零", code == 1, f"exit={code}")

    gui_smoke(real)

    for name, ok, detail in RESULTS:
        print(f"{'✓' if ok else '✗'} {name}" + (f"——{detail}" if detail and not ok else ""))
    bad = [name for name, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} 通过。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
