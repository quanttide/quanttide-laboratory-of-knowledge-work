# quanttide-laboratory-of-knowledge-work

量潮知识工作实验室——知识工作实验与原型。

## 一个程序：kg

找得到（索引）、看得见（记录）、核得动（判据）。

```bash
./kg --help              # 本目录下直接跑；八个动作
uv pip install -e .      # 或装成命令：kg --help
```

| 动作 | 干什么 |
|------|--------|
| `kg find <名字>` | 按名找文档——认文件名与中文标题 |
| `kg list` | 列全库，可导 JSON |
| `kg check` | 对账——契约有而仓库无、仓库有而契约无 |
| `kg material [路径…]` | 看材料——类型、内容、来源、时间，阶段由位置承担 |
| `kg new-contract` / `kg new-dossier` | 写契约骨架 / 案卷骨架 |
| `kg audit-contract` / `kg audit-dossier` | 核对契约（段位 + 机械核对 + 闸门） / 核对案卷 |

默认工作区从当前目录往上找，`--root` 可指向别的第二大脑。

## 目录

- `src/kg/` 程序：assets（契约层）、catalog（目录层）、checks（判据）、material（材料）、records（两种记录）、cli（入口）
- `tests/` 自带测试：`python3 tests/test_kg.py`，17 项，不依赖 pytest
- `samples/` 真实契约与案卷——判例，也是格式自证
- `docs/` 说明：模式与记录（index.md）、用户指南、开发计划

## 许可

[CC BY 4.0](LICENSE)
