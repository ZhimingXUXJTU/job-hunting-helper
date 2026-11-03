# outputs/ 说明

`run_workflow.py` 与提示词 03 的产物写在这里，**真实产物只进 `private/`**：

```
outputs/
  private/<job_id>/
    resume-draft.md    # 岗位版简历草稿（重组自事实库，needs_proof 集中在文末）
    outreach.md        # 开场文案骨架（人工补细节）
    interview-prep.md  # 面试准备（必答题、预测追问、证据索引）
  templates/           # 格式示例（虚构）
  README.md            # 本文件
```

## 纪律

- 草稿不是可投递版本：人工核对每一行、处理完 needs_proof 后另存正式版（如 `resume-v2.md`），
  并把版本号登记到 `applications/private/tracker.csv` 的 `resume_version` 列。
- 产物内容必须可溯源到 `candidate/private/facts.yml`；发现无来源内容按 needs_proof 处理。
