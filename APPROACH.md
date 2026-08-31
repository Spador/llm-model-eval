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


## Step 2: Fixing the prompt and doing the cost math

**Doing:** Locking the exact request that will go to every model, then turning the constraints into a price ceiling I can filter a leaderboard with.

### The prompt

System and schema are identical on every call. Only the question changes.

```
SYSTEM:
You are a text-to-SQL generator. Given a database schema and a question,
return a single SQL query that answers it. Use SQLite syntax.
Return only the SQL query.

USER:
Schema:
CREATE TABLE "matches" (
  "id" INTEGER, "season" TEXT, "city" TEXT, "date" TIMESTAMP,
  "match_type" TEXT, "player_of_match" TEXT, "venue" TEXT,
  "team1" TEXT, "team2" TEXT, "toss_winner" TEXT, "toss_decision" TEXT,
  "winner" TEXT, "result" TEXT, "result_margin" REAL, "target_runs" REAL,
  "target_overs" REAL, "super_over" TEXT, "method" TEXT,
  "umpire1" TEXT, "umpire2" TEXT
);
CREATE TABLE "deliveries" (
  "match_id" INTEGER, "inning" INTEGER, "batting_team" TEXT,
  "bowling_team" TEXT, "over" INTEGER, "ball" INTEGER, "batter" TEXT,
  "bowler" TEXT, "non_striker" TEXT, "batsman_runs" INTEGER,
  "extra_runs" INTEGER, "total_runs" INTEGER, "extras_type" TEXT,
  "is_wicket" INTEGER, "player_dismissed" TEXT, "dismissal_kind" TEXT,
  "fielder" TEXT
);

Question: Which bowler has the best economy rate among bowlers who bowled
at least 500 legal balls? Economy is runs conceded per over (six legal
balls). Exclude wides and no-balls from the ball count. Give the bowler
and the economy.
```

Expected output shape:

```sql
SELECT bowler,
       6.0 * SUM(total_runs) /
       SUM(CASE WHEN extras_type IS NULL
                  OR extras_type NOT IN ('wides', 'noballs')
                THEN 1 ELSE 0 END) AS economy
FROM deliveries
GROUP BY bowler
HAVING SUM(CASE WHEN extras_type IS NULL
                  OR extras_type NOT IN ('wides', 'noballs')
                THEN 1 ELSE 0 END) >= 500
ORDER BY economy ASC
LIMIT 1;
```

**Reasoning:** Two tables plus an instruction is a small, fixed prefix, so input size does not vary with the question. That makes the token count predictable enough to budget against. It also means every model is judged on identical input, so accuracy differences come from the model and not the prompt.

### Inputs to the math

| Item | Value |
|---|---|
| Input | ~400 tokens per question |
| Output | ~100 tokens per question |
| Volume | ~50,000 questions per day in season |
| Budget | 5000 USD per month |

### Monthly volume

- 50,000 x 30 = **1.5M questions per month**
- Input: 1.5M x 400 = **600M tokens**
- Output: 1.5M x 100 = **150M tokens**
- Total: **750M tokens per month**

### Ceilings

- Per question: 5000 / 1.5M = **$0.0033 per question**
- Blended, treating all tokens at one price: 5000 / 750M = **$6.67 per million tokens**

Input and output are priced separately, so the real filter is:

```
600 * P_in + 150 * P_out <= 5000
```

Dividing by 150 gives a one line rule to apply to any leaderboard row, with prices in USD per million tokens:

```
4 * P_in + P_out <= 33.3
```

Worked example: if a model prices output at 4x input, this reduces to 8 * P_in <= 33.3, so input must be at or under **$4.17 per million**.

**Output:** A hard price filter to apply during shortlisting, plus the observation that input tokens are 80 percent of monthly volume, so input price dominates the bill.


## Step 3: Choosing a leaderboard

**Doing:** Finding a leaderboard to shortlist candidates from.

Started with the obvious choice, text to SQL benchmarks:

- **Spider** (Yale), the original cross domain one. Closed to new submissions since Feb 2024.
- **Spider 2.0**, enterprise scale. 1000+ column schemas, BigQuery and Snowflake.
- **BIRD-SQL**, 12k question and SQL pairs across 95 databases.
- **WikiSQL**, superseded.

Dropped all of them:

- The top entries are not plain models. They are full systems that add extra steps around the model, like picking relevant tables first or generating several queries and voting on the best one. I need a single model answering a single prompt, so their scores do not apply to me.
- Many of the listed models are fine tuned versions built for the benchmark. I cannot call those through an API.
- These leaderboards only rank accuracy. They do not show price or speed, and those are two of my three constraints.
- The difficulty does not match my case. Spider 2.0 uses databases with over 1000 columns, while mine has two tables and 37 columns. A score there tells me little about my schema.

So I used a coding leaderboard instead. Writing SQL is a coding task, so general coding ability is a reasonable signal here. These leaderboards are updated regularly. The models on them are public ones I can call through an API. They also list price and speed, which I need for the cost filter from step 2.

**Chose:** llm-stats.com, Best AI for Coding.

**Output:** a candidate pool with accuracy, price and speed for each model.

![Best AI for Coding leaderboard, llm-stats.com](docs/img/leaderboard.png)


## Step 4: Filtering by cost and ranking the candidates

**Doing:** Removing every model that breaks the budget, then ranking what is left on accuracy and speed.

### Why the blended price works here

The leaderboard lists price as a 4:1 blend, meaning it assumes four input tokens for every one output token. My own usage is 400 input tokens and 100 output tokens, which is also 4:1. Since the ratios match, I can use the listed blended price directly instead of splitting input and output pricing per model.

### Cost per model

```
tokens per request  = 400 + 100 = 500
requests per month  = 50,000 x 30 = 1,500,000
tokens per month    = 500 x 1,500,000 = 750,000,000 = 750M
```

Prices are quoted per million tokens, so:

```
monthly cost = 750 x blended price per million
```

Setting that against the budget:

```
750 x price <= 5000
price <= 5000 / 750
price <= $6.67 per million tokens
```

**That is the filter.** Any model priced above 6.67 dollars per million blended tokens cannot run this feature at 50k questions a day. It gets dropped before I look at its accuracy at all.

Illustrative check: a model at 3.00 dollars per million costs 750 x 3 = 2250 dollars a month, so it passes with room left. A model at 10.00 costs 7500 a month and is out.

### Ranking what survives

Two columns matter now, the coding rating and the latency. They are on different scales, so I normalize both to a 0 to 1 range before combining them.

**Rating**, where higher is better:

```
normalized rating = (rating - min rating) / (max rating - min rating)
```

**Latency**, where lower is better, so the formula is inverted:

```
normalized latency = (max latency - latency) / (max latency - min latency)
```

Both now read the same way. 1 is the best model in that column and 0 is the worst.

### Combining them

```
score = 0.9 x normalized rating + 0.1 x normalized latency
```

**Why 90 to 10.** Correctness is the stated top priority, since a wrong stat gets screenshotted and shared. Latency still counts but it cannot outweigh accuracy. The output is only about 100 tokens, so even a slower model finishes a query quickly. If the feature were generating a long essay, generation speed would compound over thousands of tokens and deserve far more weight. For a short query it does not.

Note that cost does not appear in this score. Cost was already applied as a hard cutoff, so every model being ranked here is affordable. Ranking cheapness on top of that would penalize a model for spending a budget I have already approved.

**Output:** the five highest scoring models, which become the candidates for the custom eval.



## Step 5: Shortlisting the candidates

**Doing:** Applying the price cap to the ranked list, then picking the finalists for the custom eval.

### The cap

From the step 2 math, the ceiling is **$6.67 per million tokens** blended at 4:1. The leaderboard already prices at 4:1 and my usage is 400 in and 100 out, which is the same ratio, so I compare against the price column directly with no conversion.

Anything above 6.67 is removed before accuracy is considered at all.

### What the cap removes

The top of the leaderboard does not survive it. GPT-5.6 Sol at $10.00, Claude Fable 5 at $18.00, and Claude Opus 4.8 at $9.00 are all out. Claude Mythos Preview has no published price or speed and is preview only, so it is not deployable either.

Worth stating plainly: the three highest rated coding models in the world are irrelevant to this problem. At 1.5M requests a month, price decides before quality gets a say.

### The six candidates

| Model | Org | Country |
|---|---|---|
| GPT-5.6 Terra | OpenAI | US |
| Kimi K3 | Moonshot AI | China |
| DeepSeek-V4-Pro-0813 | DeepSeek | China |
| Qwen3.8 Max | Alibaba | China |
| Grok 4.6 | xAI | US |
| Claude Sonnet 5 | Anthropic | US |

**Why these six.** All sit within the price cap and rank well on the combined score. Beyond that I deliberately spread the selection across labs and countries rather than taking the top six by score. Models from the same lab tend to share training data, tokenizers, and post training recipes, so six variants of one family would tell me far less than six independent ones. If a shared weakness on my schema exists, a diverse set is what exposes it.

**Why six and not five.** The extra candidate costs one more pass over the golden dataset, which is cheap compared to the information it adds.

**Output:** six models to run the custom eval against.


## Step 6: Building the database and the golden dataset

**Doing:** Setting up the database the queries run against, extracting the schema for the prompt, and creating the question set the models are graded on.

### The database

Source is the IPL complete dataset from Kaggle, two CSVs: `matches.csv` at one row per match, and `deliveries.csv` at one row per ball bowled.

`src/db.py` filters both to seasons 2021 to 2024 and loads them into SQLite. Four seasons keeps the database small enough to commit and query instantly, while still supporting aggregation across years. The full history would slow the eval down without making it more informative.

One thing worth noting on the filter. The `season` column is inconsistent in the raw data, some rows read "2021" and others "2020/21", so filtering on that string is unreliable. I filtered on the parsed match date instead and took the year from it.

Result:

```
matches 2021-2024: 279
deliveries: 67303
orphan deliveries (should be 0): 0
date range: ('2021-04-09 00:00:00', '2024-05-26 00:00:00')
seasons: ['2021', '2022', '2023', '2024']
```

The orphan check confirms every delivery links to a match that survived the filter. And the season values came out as clean four digit years in this slice, so a model can write `season = '2023'` and it will work. One less source of failure than I expected.

### The schema

`src/schema_extractor.py` pulls the CREATE TABLE statements straight from the built database and writes `data/schema.sql`. The schema text goes into every prompt, so it has to come from the real database rather than being typed by hand.

It came out at 84 words across two tables, which sits comfortably inside the roughly 400 token context budget from step 2.

The extractor also prints sample rows and the distinct values of the string columns, which matters for the next part.

### Value domains

The schema shows column names and types but not what the string columns actually contain. A model has to guess those, and a wrong guess returns zero rows silently instead of raising an error. So I pulled them:

```
extras_type:     [None, 'noballs', 'wides', 'legbyes', 'byes']
dismissal_kind:  [None, 'run out', 'caught', 'caught and bowled', 'lbw',
                  'bowled', 'stumped', 'hit wicket', 'retired hurt',
                  'retired out', 'obstructing the field']
```

Two things follow from this. `extras_type` is NULL on ordinary deliveries rather than empty or zero, so any query counting legal balls has to handle NULL explicitly. A plain `WHERE extras_type NOT IN ('wides','noballs')` drops every normal ball, because NULL comparisons in SQL evaluate to NULL rather than true. That is the single biggest trap in this dataset and several questions are built around it.

And the values are space separated lowercase, `'run out'` not `'run_out'`, `'wides'` not `'wide'`. Exact strings matter.

### The golden dataset

20 questions, split 8 hard and 12 brutal, defined in `src/golden_dataset_generator.py`. Each entry is the natural language question plus the reference SQL that answers it.

This is deliberately a stress tier with no easy or medium questions. The point is to separate the six candidates, and simple lookups would not do that, since every frontier model handles those. The gradient is by how many traps compound in one query:

- **hard**, 1 to 2 traps: a ratio, or a NULL filter, or a HAVING threshold, or a self join
- **brutal**, 3 or more: ratios plus NULL handling plus thresholds plus subqueries plus cricket domain rules

The traps being tested: NULL sensitive filtering, rate and ratio computation, HAVING thresholds, legal ball counting, wicket attribution excluding run outs, multi level subqueries, self referential team logic on team1, team2, and winner, and innings phase logic for powerplay and death overs.

Domain definitions are spelled out inside the questions themselves. Question 10 states that economy is runs per over of six legal balls and that wides and no balls are excluded. That is intentional, the eval is testing SQL construction, not whether a model knows cricket.

### How the gold SQL was written

Ideally a human expert with domain knowledge writes and verifies every gold query. The golden dataset is the ground truth for the entire eval, so an error in it silently corrupts every score that follows.

Given time and resource constraints, I used a stronger model, Claude Opus 5, to draft the queries, then executed every one against the database to confirm it runs and returns a sensible result.

This is a real limitation and I am recording it as one. A model generated ground truth can encode the same misunderstanding of the schema that I am testing other models for. It also risks favouring candidates that reason similarly to the model that wrote the answers. Executing every query catches syntax errors and empty results, but it cannot catch a query that runs cleanly and answers a subtly different question than the one asked.

### Validation

All 20 queries execute and return non empty results:

```
[hard  ] # 4  OK  rows=1   sample=('YS Chahal', 1391)
[brutal] #10  OK  rows=1   sample=('SP Narine', 6.758139534883721)
[brutal] #12  OK  rows=4   sample=('2021', 'Chennai Super Kings', 2733)
[brutal] #19  OK  rows=1   sample=('DL Chahar', 'Shubman Gill', 4)

20/20 passed
spread: {'hard': 8, 'brutal': 12}
```

Spot checking a few against cricket knowledge: Chahal topping legal balls bowled, Narine with the best economy, Karthik leading death over runs, Russell with the best bowling average. All plausible for these seasons, which is a weak but real signal that the queries answer the questions asked.

Question 12 returns four rows, one per season, and the rest return one. That variation is deliberate, since the evaluator has to handle multi row results and not just single answers.

**Output:** `data/ipl_2021_2024.db`, `data/schema.sql`, and 20 validated questions with reference SQL.

### Limitations to carry forward

- 20 questions is a small sample. The confidence interval on any accuracy figure will be wide, and a one or two question gap between models is noise.
- Ground truth is model generated, not expert verified.
- No easy or medium tier, so aggregate accuracy will look low compared to a public leaderboard and is not comparable to one.