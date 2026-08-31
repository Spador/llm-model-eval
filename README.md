## Problem Statement

You are building a feature for a cricket statistics website of the kind
sports fans use during a live match. Today, finding a specific stat means
navigating a series of filters: pick a season, pick a team, pick a player,
pick a metric. Most users give up before they get there.

Product wants users to be able to type the question directly:

- How many sixes did Virat Kohli hit in the last 4 seasons?
- Which bowler took the most wickets in the 2023 season?
- What is the win percentage of Mumbai Indians while chasing?

The answer must come from the match database the site already maintains,
and it must be the same number the site would show anywhere else.

Constraints given by the business:

| Constraint          | Value |
|---------------------|-------|
| Budget              | 5000 USD per month for this feature |
| Correctness         | Highest priority. Fans screenshot stats and post them. A wrong number becomes a public credibility problem |
| Latency             | Should feel fast. Lower weight than correctness |
| Daily Questions     | About 50k |


Deliverable: a recommendation for which model to use, with the evidence
behind the choice.