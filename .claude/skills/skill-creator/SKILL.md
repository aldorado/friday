---
name: skill-creator
description: Use when asked to create a new skill, add a capability, or when you identify a recurring task that would benefit from a skill. Also use when discussing skill structure or troubleshooting skills.
---

# Skill Creator

Create new skills for jarvis following the claude code skills standard.

## Before Creating a Skill

**Always ask the user first.** Clarify:
- what the skill should do
- suggested name
- whether it should auto-trigger or be manual-only

## Skill Location

All jarvis skills go in: `.claude/skills/<skill-name>/SKILL.md`

## SKILL.md Structure

Every skill needs a `SKILL.md` with yaml frontmatter:

```yaml
---
name: skill-name                        # lowercase, hyphens, max 64 chars
description: When to use this skill...  # include trigger phrases
# optional fields below:
disable-model-invocation: false         # true = only user can invoke via /skill-name
user-invocable: true                    # false = only claude can auto-invoke
argument-hint: "[arg1] [arg2]"          # hint for autocomplete
context: fork                           # run in isolated subagent
agent: Explore                          # subagent type (with context: fork)
---

# Skill Title

Clear instructions for what to do when this skill is invoked.

## Additional Resources

Reference supporting files if needed:
- [references/detailed-docs.md](references/detailed-docs.md)
```

## Key Frontmatter Fields

| Field | Use When |
|-------|----------|
| `disable-model-invocation: true` | skill has side effects (deploy, send message, commit) |
| `user-invocable: false` | background knowledge only, not a command |
| `context: fork` | heavy research task that needs isolated context |
| `argument-hint` | skill takes arguments like `/skill issue-123` |

## Note on Permissions

Jarvis runs with bypass permissions, so `allowed-tools` is only needed if you want to *restrict* a skill (e.g., read-only skill). Otherwise, omit it.

## Directory Structure

For simple skills:
```
skill-name/
└── SKILL.md
```

For complex skills:
```
skill-name/
├── SKILL.md
├── references/          # detailed docs
│   └── patterns.md
├── examples/            # code examples
│   └── example.py
└── scripts/             # utility scripts
    └── helper.sh
```

## Writing Good Descriptions

Include specific trigger phrases:
```yaml
# good
description: Use when asked to "deploy the app", "push to production", or "release"

# bad
description: Handles deployment
```

## Dynamic Context

Skills can inject live data using `!`command`` syntax:
```markdown
Current git status: !`git status --short`
```

This executes before the skill loads and inserts the output.

## Workflow

1. Discuss with the user what the skill should do
2. Create directory: `.claude/skills/<name>/`
3. Write SKILL.md with frontmatter + instructions
4. Add references/ if detailed docs needed
5. Test by invoking `/skill-name` or triggering naturally
6. Commit and push changes

## Reference

For full frontmatter options and advanced patterns, see [references/frontmatter.md](references/frontmatter.md)
