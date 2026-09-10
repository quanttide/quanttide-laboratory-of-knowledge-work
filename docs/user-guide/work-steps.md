# 工作步骤

拿真事说话：2026-09-10 那次「个人课程档案 × 课程研发档案」的比对。七步走完，命令都在终端里跑过。

## 1 找源

```bash
kg find 课程                      # 按名找：认文件名与中文标题
ls data/profile/iGuo/course/      # 一边：work 侧的个人课程档案
grep -rln "课程研发" /home/iguo/repos/quanttide    # 另一边在别的仓库里
```

两边都得指得出确切路径——文件在哪、里面有什么，先摆清楚再谈比对。

## 2 立流程

```bash
kg workflow --new 课程档案比对 --steps 定位,比对,结论 --note "比对两边的档案"
```

数据按三家落地：

```text
data/workflows/课程档案比对.md     工作流：串联的步骤（每步自带判据）
data/tasks/课程档案比对.md         任务：这一次的执行（跑哪条工作流、要什么）
data/artifacts/课程档案比对/       产物：log.jsonl、report.md、history.md
```

工作流是**数据不是代码**：步骤写在这份文件里，程序不预置。

## 3 写步骤的判据

工作流里每步一段，判据写在步骤下面——不写进代码：

```markdown
### 定位

- 做什么：把两边的源找齐
- [ ] 机械：个人课程档案在 `path:data/profile/iGuo/course/index.md`
- [ ] 机械：课程研发档案在 `path:/…/quanttide-course/data/profile/README.md`
- [ ] 闸门：创始人点头（回流与并法怎么定）
```

机械的当场判（存在、不存在、含某段文字、跑一条命令）；闸门的列出来留给人。

## 4 起一件任务，干活

```bash
$ kg task --new 课程档案比对 --workflow 课程档案比对 --about "比对 work 侧与课程研发档案"
起了：…/data/tasks/课程档案比对.md
```

真正的判断在这儿发生——CLI 不替你想。这次比的四条：口径不同（一边记「为什么这么办」，一边记「课里有什么」）、两边都有的课、各自的缺口、格式差（可机读 vs 散文）。

产物写进 `data/artifacts/课程档案比对/比对.md`。

## 5 一步一记

```bash
$ kg task 课程档案比对 --done 定位 --note "work 侧 3 件、course 侧 3 门课"
✓ 定位：work 侧 3 件、course 侧 3 门课
  ✓ 机械：个人课程档案在（path:data/profile/iGuo/course/index.md）
  ✓ 机械：课程研发档案在（path:/…/course/data/profile/README.md）
下一步：比对
```

`--done <步骤>` 做三件事：跑这一步的机械判据、记一笔流水、刷新报告。没有判据的步骤也能记一笔（`--note` 一句话）。

## 6 看

```bash
$ kg task 课程档案比对
  ✓ 定位   ✓ 比对   ✓ 结论
3 个步骤都走过了

$ cat data/artifacts/课程档案比对/report.md      # 执行记录 + 闸门项，机器写
```

## 7 收尾

闸门项留着等你拍板（这次是「回流与并法怎么定」）；这一趟的来龙去脉写进历史：

```bash
kg task 课程档案比对 --history "先找齐两边，再按口径/重叠/缺口/格式差四条比……"
```

## 窗口里也一样

`./kg-gui` 台面：上方选一次运行，中间是步骤表（步骤 / 关联的任务 / 状态，双击打开那个任务），填一句「这一步做了什么」，点「执行这一步」——同一套动作，同一份数据。

## 规矩

- **数据全落 `data/`**（workflows / tasks / artifacts 三家），不写实验室外面；
- **判据写进验收**，模板里的占位（`<…>`）不算判据；
- **工作流是数据**：不预置、不累积；改顺序或加减步骤，改 `data/workflows/<工作流>.md`；
- **别人的仓库不擅动**：course 侧属另一个仓库，动它要授权。
