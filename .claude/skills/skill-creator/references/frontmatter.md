# YAML Frontmatter Reference

Complete reference for all skill frontmatter fields.

## Required Fields

### name
- **Type:** string
- **Format:** lowercase letters, numbers, hyphens only, max 64 chars
- **Default:** directory name if omitted
- **Example:** `name: deploy-app`

### description
- **Type:** string (max 1024 chars)
- **Purpose:** tells claude when to auto-trigger the skill
- **Best practice:** include specific trigger phrases users would say

```yaml
description: Use when user asks to "create a PR", "open pull request", or "submit changes for review"
```

## Optional Fields

### disable-model-invocation
- **Type:** boolean
- **Default:** false
- **Use when:** skill has side effects (deploys, sends messages, commits)
- **Effect:** only user can invoke via `/skill-name`, claude won't auto-trigger

### user-invocable
- **Type:** boolean
- **Default:** true
- **Use when:** skill is background knowledge, not a command
- **Effect:** skill won't appear in `/` menu, only claude can invoke

### argument-hint
- **Type:** string
- **Purpose:** autocomplete hint shown after `/skill-name`
- **Example:** `argument-hint: "[issue-number]"` shows as `/my-skill [issue-number]`

### context
- **Type:** string
- **Value:** `"fork"` to run in isolated subagent
- **Use when:** heavy research tasks, need fresh context
- **Effect:** skill runs in subagent without conversation history

### agent
- **Type:** string
- **Values:** `Explore`, `Plan`, `general-purpose`, or custom agent name
- **Use with:** `context: fork`
- **Purpose:** specify which subagent type handles the skill

### allowed-tools
- **Type:** string or array
- **Purpose:** RESTRICT which tools skill can use
- **Note:** only use if you want to limit access (jarvis has bypass permissions)

```yaml
# string format
allowed-tools: Read, Grep, Glob

# array format
allowed-tools:
  - Read
  - Grep
  - Bash(git:*)
```

### model
- **Type:** string
- **Purpose:** override model for this skill
- **Example:** `model: claude-opus-4-5-20251101`

### hooks
- **Type:** object
- **Purpose:** skill-scoped event hooks
- **Events:** PreToolUse, PostToolUse, Stop, etc.

```yaml
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: prompt
          prompt: "Verify this is safe: $TOOL_INPUT"
```

## String Substitutions

Available in skill content:
- `$ARGUMENTS` - arguments passed when invoking (e.g., `/skill arg1 arg2`)
- `${CLAUDE_SESSION_ID}` - current session ID
- `!`command`` - execute shell command, insert output

## Invocation Control Matrix

| Settings | User Can Invoke | Claude Can Invoke |
|----------|-----------------|-------------------|
| (default) | ✅ | ✅ |
| `disable-model-invocation: true` | ✅ | ❌ |
| `user-invocable: false` | ❌ | ✅ |
| both | ❌ | ❌ (reference only) |
