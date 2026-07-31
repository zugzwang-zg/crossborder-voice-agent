# CrossBorder Voice demo guide

Recommended duration: 90 seconds.

## Narrative

CrossBorder Voice analyzes English and Spanish beauty reviews and converts them into traceable product, fulfillment and content insights.

Start with the dashboard overview. The dataset contains 1,000 deterministically sampled reviews, balanced by language and star rating. Star ratings and model-derived sentiment are shown separately because a high rating may still contain uncertainty or criticism.

Open the aspect and issue views to compare what reviewers discuss. Filters allow the analysis to be narrowed by language, rating, sentiment, aspect, issue and scenario.

Next, open an insight card. Each insight retains its supporting count, language distribution, source review IDs and representative quotes. This makes the route from aggregate claim to original evidence explicit.

Finally, show the evaluation report. The improved prompt reached 100% JSON success, 89% sentiment accuracy, 74.02% aspect F1 and 96% semantic evidence validity on the frozen evaluation protocol. The interface and reports also state the main limits: historical source data, a small neutral class, and no causal interpretation of cross-language differences.

The system is designed as a human-in-the-loop evidence tool: the agent structures and retrieves evidence; domain users make the final business judgment.
