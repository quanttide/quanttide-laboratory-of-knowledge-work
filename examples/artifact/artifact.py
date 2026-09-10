"""Artifact 最小模型：验证 docs/specification/piece/artifact.md 与 docs/handbook/artifacts/index.md 的定义。

规格要点：产物有规格并以此验收；角色唯一；三段式流动（接收→加工→转出）；
单一去处；不留副本，上游净缩短；转出内容在下游可再找到。

用真实样本验证：2026-09-10 日志「产教融合想法」转入档案 qtclass。
"""

from dataclasses import dataclass


@dataclass
class Artifact:
    """产物：工作物的最小模型。角色唯一，内容只向下游流动。"""

    role: str
    content: str = ""

    def receive(self, text: str) -> None:
        """接收上游转出的内容，登记到本地。"""
        self.content = (self.content + "\n" + text).strip()

    def transfer(self, downstream: "Artifact", text: str) -> None:
        """转出：单一去处，上游不留副本、净缩短，下游可再找到。"""
        if text not in self.content:
            raise ValueError(f"{self.role} 中不存在要转出的内容")
        downstream.receive(text)
        self.content = "\n".join(line for line in self.content.replace(text, "").splitlines() if line.strip())


# 一个产物 = 一个角色（角色唯一）
journal = Artifact(role="journal")
profile = Artifact(role="profile")

# 接收：日志捕获口述原料
journal.receive("产教融合：知识工作课程体系就用这个体系来支持，量潮课堂来验证。")
assert "产教融合" in journal.content

# 转出：整理到档案（今天的真实流动：journal → profile/qtclass）
journal.transfer(profile, "产教融合：知识工作课程体系就用这个体系来支持，量潮课堂来验证。")

# 验收三条规格判据
assert "产教融合" not in journal.content, "上游不留副本，净缩短"
assert "产教融合" in profile.content, "转出内容在下游可再找到"
try:
    journal.transfer(insight := Artifact(role="insight"), "产教融合")
    raise AssertionError("每条内容每次流动只有一个去处")
except ValueError:
    pass

print("验证通过：产物 = 角色 + 内容，流动满足单一去处、不留副本、下游可再找到。")
