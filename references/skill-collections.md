# 技能集合（可选进阶）

如果你要做的不是单个技能，而是一组相关技能（比如一个"品牌官网全流程"包含 brand-design / copywriting / seo-audit / dev-deploy 五个），参考高星仓库（superpowers、brand-build 59-skill library、antigravity-awesome-skills 1400+）的做法：

```
my-collection/
├── SKILL.md              # meta-skill：路由入口，告诉模型"用户要做品牌相关的事时先读我"
├── skills/
│   ├── brand-design/SKILL.md
│   ├── copywriting/SKILL.md
│   ├── seo-audit/SKILL.md
│   └── dev-deploy/SKILL.md
└── scripts/              # 集合级共享脚本
```

## 要点

- meta-skill 的 SKILL.md 只做一件事：根据用户意图路由到具体子技能，不要把子技能的指令复制进来。
- 每个子技能仍然是独立的、可单独触发的，description 各自写清楚。
- 集合里可以放一个 meta-skill 专门教用户怎么在这个集合里再加新技能（参考 brand-build 仓库的做法）。
- 这种形态适合一上来就知道要做一整套方法论的场景；如果只是先做一个技能，别过度设计。

## 国内生态补充

国内小红书/抖音上走红的技能很多是"视觉风格包"形态——一个 SKILL.md 描述风格 + assets/ 里放参考图/关键词库，没有 scripts 也没有 evals。这类属于轻量技能（见主文件"轻量 vs 重量流程"），不要硬套完整 eval 闭环。
