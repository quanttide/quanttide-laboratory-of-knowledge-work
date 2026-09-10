"""产物流动检查：扫描真实工作物目录，抓出违反流动判据的内容副本。

用法：python3 artifact.py [目录 ...]
不传参数时检查仓库的 data/{journal,profile,intention,insight}。

依据 docs/handbook/artifacts/index.md：「不留副本，转出后上游不以原形式留存；
单一去处」。两条合并为一条可检查的硬判据——同一行内容只应存在于一个产物中。
产物角色 = 所有被扫文件共同父目录之下的一级目录名。
"""

import os
import sys
from pathlib import Path

MIN_CHARS = 12  # 短于此的行多为标题与套话，不参与比对


def load(roots):
    """返回 {内容行: [(角色, 路径, 行号), ...]}。"""
    files = sorted({p for root in roots for p in root.rglob("*.md")})
    base = Path(os.path.commonpath([f.parent for f in files]))
    pieces = {}
    for path in files:
        if path.name == "README.md":
            continue  # 仓库门面，非工作物内容
        rel = path.relative_to(base)
        role = rel.parts[0] if len(rel.parts) > 1 else base.name
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if len(line) < MIN_CHARS or line.startswith("#"):
                continue
            pieces.setdefault(line, []).append((role, path, no))
    return pieces


def main(roots):
    pieces = load(roots)
    copies = {
        text: locs
        for text, locs in pieces.items()
        if len({role for role, _, _ in locs}) > 1
    }
    for text, locs in sorted(copies.items()):
        print(f"副本：{text[:48]}{'…' if len(text) > 48 else ''}")
        for role, path, no in locs:
            print(f"  {role}: {path}:{no}")
    if not copies:
        print("流动干净：无跨产物副本。")
    return 1 if copies else 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        roots = [Path(arg) for arg in sys.argv[1:]]
    else:
        repo = Path(__file__).resolve().parent
        while not (repo / "data" / "journal").exists():
            repo = repo.parent
        data = repo / "data"
        roots = [data / role for role in ("journal", "profile", "intention", "insight") if (data / role).is_dir()]
    sys.exit(main(roots))
