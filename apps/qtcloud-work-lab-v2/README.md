# qtcloud-work-lab-v2

量潮知识工作实验室 v2——按规格重写的工作流与工单。

中心是**工单**：一条工作流的一次执行实例；命令里的每个动作，就是走其中一站。模型与行为差见[设计](docs/index.md)，里程碑与决策见[开发计划](docs/dev-guide/index.md)，动作对表见[用法](docs/user-guide/index.md)。

## 一个程序：kg

```bash
./kg workflow create 课程档案比对 --steps 定位,比对,结论 --description "比对两边的档案"
./kg order create 课程档案比对 --workflow 课程档案比对 --description "比对两侧课程档案"
./kg order next 课程档案比对           # 走下一步：智能体执行，程序核 rule 判据
./kg order done 课程档案比对 结论       # 人记一笔（闸门放行也走这里）
./kg order show 课程档案比对            # 全貌：封面加全量流水
uv pip install -e .                    # 或装成命令：kg
```

| 动作 | 干什么 |
|------|--------|
| `kg workflow create <名字> --steps 甲,乙,丙` | 写一条工作流：步骤带全局 `id`，各写一份判据骨架 |
| `kg workflow show <名字>` / `kg workflow list` | 看步骤与判据 / 有哪些工作流 |
| `kg workflow check <名字>` | 定义核对：判据路径在不在区内、小节有没有判据覆盖 |
| `kg workflow export <名字> <文件>` / `kg workflow import <文件> [--as 名字]` | 原样存走 / 导进来用（按 schema 验、重名挡） |
| `kg order create <名字> --workflow <工作流>` | 开工单：封面落笔即封，凭证与时刻账本方查填 |
| `kg order show <名字>` / `kg order list [--json]` | 读全貌（封面加流水）/ 列工单，可按工作流筛 |
| `kg order next <名字>` | 走下一步：智能体执行，程序核 `rule` 判据，记一条工作记录 |
| `kg order done <名字> <步骤>` | 人记一笔；带 `human` 判据的闸门站，放行也走这里 |
| `kg order journal <名字> <一段话>` | 日志：叙事落产物，不动流水 |
| `kg order delete <名字>` | 删一张白纸——流水非空即拒，账本不销户 |

工作区不进命令行：从当前目录往上找 `workspace.yaml`，找不到就用本 app 的 `data/`；`--root` 可另指一处。

## 目录

- `src/kg/` 程序：workspace（工作区身份与落点）、workflow（工作流与工作步骤）、workorder（工单与工作记录）、checks（判据）、execute（走一步：智能体执行与人记一笔）、events（领域事件）、artifacts（产物）、actions（动作层）、cli（命令行入口）
- `data/` 所有数据（工作纪律，见 `AGENTS.md`）
- `tests/` 自带测试：`python3 tests/test_kg.py`，不依赖 pytest
- `docs/` 说明：设计、开发计划、用法

## 许可

[CC BY 4.0](LICENSE)
