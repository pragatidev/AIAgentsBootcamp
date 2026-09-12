# TalentFlow document pipeline starter

Map-reduce over the resumes in `talentflow/data`, plus the job description and the email templates.

Fill the TODO bodies in `graph.py` (load, score, summarize). `fan_out` is wired. The plant: `scores` has no reducer, so the fan-in collides with InvalidUpdateError. Add `Annotated[list, operator.add]`, then N resumes score and one summary prints.

## Test with no key

From the course repo root:

```
pytest labs/19_talentflow/starter/check -q
```

The model comes from course `config.py`. Email templates live in `talentflow/data/templates`.
