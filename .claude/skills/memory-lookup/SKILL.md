---
name: memory-lookup
description: Internal skill to retrieve relevant memories for any topic. Use proactively when context about the user's preferences, projects, or past decisions could be helpful.
---

# Memory Lookup

You have a semantic memory system stored in `data/memories.parquet`. Use this skill to search your memories when you need context.

## When to use this

Use this proactively when:
- user mentions a topic you might have stored info about
- you need to recall preferences, past decisions, project details
- user references something from the past
- context would help you give a better response

## How to search

Run a Python script to search memories:

```bash
uv run python -c "
from jarvis.memory import MemoryManager
m = MemoryManager()
results = m.search('YOUR_QUERY_HERE')
for r in results:
    print(f\"[{r['similarity']:.2f}] {r['created_at'][:10]}\")
    print(r['content'])
    print('---')
"
```

Replace `YOUR_QUERY_HERE` with your search query. Be specific - the semantic search works better with detailed queries.

## Settings

Default: threshold=0.3, always returns at least 3 results (top matches even if below threshold).

```bash
results = m.search('query', threshold=0.4)  # stricter matching
results = m.search('query', min_results=5)  # more fallback results
```

## Output

Returns memories with:
- similarity score (0-1)
- created date
- full content

Use the content to inform your response. Don't mention the lookup mechanics to the user - just naturally incorporate the context.
