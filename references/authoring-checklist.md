# 技能作者自检清单（写完 SKILL.md 后过一遍）

参考 obra/superpowers 实战沉淀。写完技能初稿后，**作者自己**过一遍这 4 步，别等用户测出来。

## 1. No Placeholders（禁止占位符）

SKILL.md 里出现以下任何一条，就是技能没写完：

- `TBD`、`TODO`、`implement later`、`fill in details`（模板里的占位符除外）
- `"add appropriate error handling"` / `"add validation"` / `"handle edge cases"`——没说具体怎么处理
- `"write tests for the above"`——没有实际测试代码
- `"similar to Task N"`——工程师可能按顺序读，必须重复写清楚
- 描述了"做什么"但没给"怎么做"（代码步骤必须贴代码）
- 引用了前面技能里没定义过的函数名/类型名

**判断标准：** 假设读者完全没有上下文，只看这份技能能不能动手做。不能就是占位符。

## 2. 触发后宣布自己在用这个技能

在 SKILL.md 开头加一句：

```
**Announce at start:** "我在用 XX 技能处理这个任务。"
```

作用：用户看到这句就知道为什么输出是这个格式，不会觉得 AI 突然"变了个人"。轻量技能（写文案、改风格）可以不加，流程型/工具型建议加。

## 3. 技能之间显式引用

如果这个技能做完后下一步必然用另一个技能，在正文里写：

```
**REQUIRED NEXT SKILL:** 完成本步后，用 `<other-skill-name>` 继续。
```

不要假设 Agent 会自己猜到下一步该用什么。显式写出来，形成技能链。

## 4. Self-Review 四步

写完整个 SKILL.md 后，用新眼光过一遍：

1. **覆盖度**：这个技能要解决的场景，每个都有对应指令了吗？漏掉的补上。
2. **占位符扫描**：全文搜 `TODO`、`TBD`、`appropriate`、`similar to`，有就改掉。
3. **一致性**：前面说的术语、文件名、命令，后面引用时名字一致吗？前面叫 `normalize.py` 后面别写成 `clean.py`。
4. **边界情况**：用户可能怎么把这个技能用歪？在 Common Pitfalls 里写出来。

发现问题直接改，不用重新评审一遍。
