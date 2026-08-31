# Approach

Step by step record of how I worked through this problem.
Results in the README.

---

## Step 1: Reading the problem

**Doing:** Defining the task from the problem statement.

**Reasoning:**
- DB already exists and is the source of truth, so the feature is a
  translation problem, not a computation one. Task is text to SQL.
- Rejected loading match data into context: model arithmetic can be
  confidently wrong, costs more, and risks numbers that disagree with the
  rest of the site. 400 token budget fits a schema, not data.
- Model owns schema comprehension and valid SQL. It does not own data
  accuracy or arithmetic. So correctness has to be measured on returned
  rows, not on query text, since two different queries can both be right.
- Priority from constraints: correctness first, cost as a hard ceiling,
  latency as a tiebreaker.

**Gaps:** query volume unspecified, no concrete schema or DB yet, traffic
shape unknown.

**Output:** Task is text to SQL. Decision rule is drop anything over
budget, pick the most accurate of the rest, latency breaks ties.