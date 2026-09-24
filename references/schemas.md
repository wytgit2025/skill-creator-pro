# JSON Schema 文档

本文档定义了 skill-creator 使用的各种 JSON 格式。

---

## evals.json

定义技能的测试用例。位于技能目录下的 `evals/evals.json`。

```json
{
  "skill_name": "example-skill",
  "evals": [
    {
      "id": 1,
      "prompt": "用户的示例提示词",
      "expected_output": "预期结果的描述",
      "files": ["evals/files/sample1.pdf"],
      "expectations": [
        "输出里包含 X",
        "技能用了脚本 Y"
      ]
    }
  ]
}
```

**字段说明：**
- `skill_name`：技能名称，和前置元数据里的一致
- `evals[].id`：唯一的整数 ID
- `evals[].prompt`：要执行的任务
- `evals[].expected_output`：人类可读的成功标准描述
- `evals[].files`：可选，输入文件路径列表（相对技能根目录）
- `evals[].expectations`：可验证的断言列表

---

## history.json

记录改进模式下的版本迭代过程。位于 workspace 根目录。

```json
{
  "started_at": "2026-01-15T10:30:00Z",
  "skill_name": "pdf",
  "current_best": "v2",
  "iterations": [
    {
      "version": "v0",
      "parent": null,
      "expectation_pass_rate": 0.65,
      "grading_result": "baseline",
      "is_current_best": false
    },
    {
      "version": "v1",
      "parent": "v0",
      "expectation_pass_rate": 0.75,
      "grading_result": "won",
      "is_current_best": false
    },
    {
      "version": "v2",
      "parent": "v1",
      "expectation_pass_rate": 0.85,
      "grading_result": "won",
      "is_current_best": true
    }
  ]
}
```

**字段说明：**
- `started_at`：改进开始的 ISO 时间戳
- `skill_name`：正在改进的技能名称
- `current_best`：当前最优版本的标识
- `iterations[].version`：版本标识（v0, v1, ...）
- `iterations[].parent`：这个版本是从哪个版本改来的
- `iterations[].expectation_pass_rate`：打分后的通过率
- `iterations[].grading_result`："baseline"（基线）、"won"（赢了）、"lost"（输了）或 "tie"（平局）
- `iterations[].is_current_best`：这个是不是当前最优版本

---

## grading.json

打分代理的输出。位于 `<run-dir>/grading.json`。

```json
{
  "expectations": [
    {
      "text": "输出里包含名字 'John Smith'",
      "passed": true,
      "evidence": "在执行记录第 3 步找到：'提取的名字：John Smith, Sarah Johnson'"
    },
    {
      "text": "表格 B10 单元格有 SUM 公式",
      "passed": false,
      "evidence": "没有创建表格。输出是一个文本文件。"
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 1,
    "total": 3,
    "pass_rate": 0.67
  },
  "execution_metrics": {
    "tool_calls": {
      "Read": 5,
      "Write": 2,
      "Bash": 8
    },
    "total_tool_calls": 15,
    "total_steps": 6,
    "errors_encountered": 0,
    "output_chars": 12450,
    "transcript_chars": 3200
  },
  "timing": {
    "executor_duration_seconds": 165.0,
    "grader_duration_seconds": 26.0,
    "total_duration_seconds": 191.0
  },
  "claims": [
    {
      "claim": "表单有 12 个可填字段",
      "type": "factual",
      "verified": true,
      "evidence": "在 field_info.json 里数到 12 个字段"
    }
  ],
  "user_notes_summary": {
    "uncertainties": ["用的是 2023 年的数据，可能过时了"],
    "needs_review": [],
    "workarounds": ["对不可填字段降级用了文本叠加"]
  },
  "eval_feedback": {
    "suggestions": [
      {
        "assertion": "输出里包含名字 'John Smith'",
        "reason": "一个幻觉出来的文档提到这个名字也能通过"
      }
    ],
    "overall": "断言只检查了存在性，没检查正确性。"
  }
}
```

**字段说明：**
- `expectations[]`：打分后的断言，带证据
- `summary`：通过/失败的汇总计数
- `execution_metrics`：工具使用和输出大小（从执行代理的 metrics.json 来）
- `timing`：实际耗时（从 timing.json 来）
- `claims`：从输出里提取并验证的声明
- `user_notes_summary`：执行代理标记的问题
- `eval_feedback`：（可选）对测试用例的改进建议，只有打分代理发现值得提的问题时才出现

---

## metrics.json

执行代理的输出。位于 `<run-dir>/outputs/metrics.json`。

```json
{
  "tool_calls": {
    "Read": 5,
    "Write": 2,
    "Bash": 8,
    "Edit": 1,
    "Glob": 2,
    "Grep": 0
  },
  "total_tool_calls": 18,
  "total_steps": 6,
  "files_created": ["filled_form.pdf", "field_values.json"],
  "errors_encountered": 0,
  "output_chars": 12450,
  "transcript_chars": 3200
}
```

**字段说明：**
- `tool_calls`：每种工具的调用次数
- `total_tool_calls`：所有工具调用总数
- `total_steps`：主要执行步骤数
- `files_created`：创建的输出文件列表
- `errors_encountered`：执行过程中遇到的错误数
- `output_chars`：输出文件总字符数
- `transcript_chars`：执行记录字符数

---

## timing.json

一次运行的实际耗时。位于 `<run-dir>/timing.json`。

**怎么采集：** 当子代理任务完成时，任务通知里会有 `total_tokens` 和 `duration_ms`。立刻保存下来——这些数据不会持久化在别的地方，事后找不回来。

```json
{
  "total_tokens": 84852,
  "duration_ms": 23332,
  "total_duration_seconds": 23.3,
  "executor_start": "2026-01-15T10:30:00Z",
  "executor_end": "2026-01-15T10:32:45Z",
  "executor_duration_seconds": 165.0,
  "grader_start": "2026-01-15T10:32:46Z",
  "grader_end": "2026-01-15T10:33:12Z",
  "grader_duration_seconds": 26.0
}
```

---

## benchmark.json

基准测试模式的输出。位于 `benchmarks/<timestamp>/benchmark.json`。

```json
{
  "metadata": {
    "skill_name": "pdf",
    "skill_path": "/path/to/pdf",
    "executor_model": "claude-sonnet-4-20250514",
    "analyzer_model": "most-capable-model",
    "timestamp": "2026-01-15T10:30:00Z",
    "evals_run": [1, 2, 3],
    "runs_per_configuration": 3
  },

  "runs": [
    {
      "eval_id": 1,
      "eval_name": "Ocean",
      "configuration": "with_skill",
      "run_number": 1,
      "result": {
        "pass_rate": 0.85,
        "passed": 6,
        "failed": 1,
        "total": 7,
        "time_seconds": 42.5,
        "tokens": 3800,
        "tool_calls": 18,
        "errors": 0
      },
      "expectations": [
        {"text": "...", "passed": true, "evidence": "..."}
      ],
      "notes": [
        "用的是 2023 年的数据，可能过时了",
        "对不可填字段降级用了文本叠加"
      ]
    }
  ],

  "run_summary": {
    "with_skill": {
      "pass_rate": {"mean": 0.85, "stddev": 0.05, "min": 0.80, "max": 0.90},
      "time_seconds": {"mean": 45.0, "stddev": 12.0, "min": 32.0, "max": 58.0},
      "tokens": {"mean": 3800, "stddev": 400, "min": 3200, "max": 4100}
    },
    "without_skill": {
      "pass_rate": {"mean": 0.35, "stddev": 0.08, "min": 0.28, "max": 0.45},
      "time_seconds": {"mean": 32.0, "stddev": 8.0, "min": 24.0, "max": 42.0},
      "tokens": {"mean": 2100, "stddev": 300, "min": 1800, "max": 2500}
    },
    "delta": {
      "pass_rate": "+0.50",
      "time_seconds": "+13.0",
      "tokens": "+1700"
    }
  },

  "notes": [
    "断言'输出是 PDF 文件'在两种配置下都是 100% 通过——可能区分不出技能价值",
    "测试用例 3 方差很大（50% ± 40%）——可能不稳定或和模型有关",
    "不带技能的运行在表格提取断言上一直失败",
    "技能平均增加 13 秒执行时间，但通过率提升了 50%"
  ]
}
```

**字段说明：**
- `metadata`：基准运行的信息
  - `skill_name`：技能名称
  - `timestamp`：基准测试运行时间
  - `evals_run`：运行的测试用例名称或 ID 列表
  - `runs_per_configuration`：每个配置跑几次（比如 3 次）
- `runs[]`：单次运行结果
  - `eval_id`：数字 ID
  - `eval_name`：人类可读的测试用例名称（在查看器里当章节标题）
  - `configuration`：必须是 `"with_skill"` 或 `"without_skill"`（查看器用这个字符串做分组和颜色编码）
  - `run_number`：整数运行次数（1, 2, 3...）
  - `result`：嵌套对象，包含 `pass_rate`、`passed`、`total`、`time_seconds`、`tokens`、`errors`
- `run_summary`：每个配置的统计汇总
  - `with_skill` / `without_skill`：各包含 `pass_rate`、`time_seconds`、`tokens` 对象，带 `mean` 和 `stddev` 字段
  - `delta`：差值字符串，比如 `"+0.50"`、`"+13.0"`、`"+1700"`
- `notes`：分析代理的自由格式观察

**重要：** 查看器严格按这些字段名读取。把 `configuration` 写成 `config`，或者把 `pass_rate` 放在 run 的顶层而不是嵌套在 `result` 里，会导致查看器显示空/零值。手动生成 benchmark.json 的时候一定要参考这个 schema。

---

## comparison.json

盲测对比的输出。位于 `<grading-dir>/comparison-N.json`。

```json
{
  "winner": "A",
  "reasoning": "输出 A 提供了完整的解决方案，格式规范，所有必填字段都在。输出 B 缺了日期字段，格式也不一致。",
  "rubric": {
    "A": {
      "content": {
        "correctness": 5,
        "completeness": 5,
        "accuracy": 4
      },
      "structure": {
        "organization": 4,
        "formatting": 5,
        "usability": 4
      },
      "content_score": 4.7,
      "structure_score": 4.3,
      "overall_score": 9.0
    },
    "B": {
      "content": {
        "correctness": 3,
        "completeness": 2,
        "accuracy": 3
      },
      "structure": {
        "organization": 3,
        "formatting": 2,
        "usability": 3
      },
      "content_score": 2.7,
      "structure_score": 2.7,
      "overall_score": 5.4
    }
  },
  "output_quality": {
    "A": {
      "score": 9,
      "strengths": ["完整方案", "格式规范", "所有字段都在"],
      "weaknesses": ["标题有小的风格不一致"]
    },
    "B": {
      "score": 5,
      "strengths": ["输出可读", "基本结构正确"],
      "weaknesses": ["缺日期字段", "格式不一致", "数据提取不全"]
    }
  },
  "expectation_results": {
    "A": {
      "passed": 4,
      "total": 5,
      "pass_rate": 0.80,
      "details": [
        {"text": "输出包含名字", "passed": true}
      ]
    },
    "B": {
      "passed": 3,
      "total": 5,
      "pass_rate": 0.60,
      "details": [
        {"text": "输出包含名字", "passed": true}
      ]
    }
  }
}
```

---

## analysis.json

事后分析代理的输出。位于 `<grading-dir>/analysis.json`。

```json
{
  "comparison_summary": {
    "winner": "A",
    "winner_skill": "path/to/winner/skill",
    "loser_skill": "path/to/loser/skill",
    "comparator_reasoning": "对比代理为什么选赢家的简短总结"
  },
  "winner_strengths": [
    "处理多页文档有清晰的分步指令",
    "包含了验证脚本，能抓到格式错误"
  ],
  "loser_weaknesses": [
    "含糊的指令'适当处理文档'导致了不一致的行为",
    "没有验证脚本，代理只能即兴发挥"
  ],
  "instruction_following": {
    "winner": {
      "score": 9,
      "issues": ["小问题：跳过了可选的日志步骤"]
    },
    "loser": {
      "score": 6,
      "issues": [
        "没有用技能的格式模板",
        "自己发明了方法而不是遵循第 3 步"
      ]
    }
  },
  "improvement_suggestions": [
    {
      "priority": "high",
      "category": "instructions",
      "suggestion": "把'适当处理文档'替换成明确步骤",
      "expected_impact": "会消除导致不一致行为的歧义"
    }
  ],
  "transcript_insights": {
    "winner_execution_pattern": "读技能 → 遵循 5 步流程 → 用验证脚本",
    "loser_execution_pattern": "读技能 → 方法不明确 → 试了 3 种不同方法"
  }
}
```
