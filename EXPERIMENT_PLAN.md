# Experiment Plan: New Landing Page Test

> **Status:** retrospective. I wrote this *after* analysing the test, to set out how it **should** have been planned. Every number below comes from this repo's analysis, and the "Lessons" section shows where the real test fell short of this plan.

## 1. Hypothesis
Changing to the new landing page will **increase sign-up conversion** compared with the current page.

- **H0 (null):** conversion(new) = conversion(old)
- **H1 (alternative):** conversion(new) ≠ conversion(old), tested two-sided so that harm can also be detected

## 2. Metrics

| Type | Metric | Why |
|---|---|---|
| **Primary** | Conversion rate (users who convert ÷ users who saw the page) | The single metric the ship decision rests on |
| Guardrail | Page load time | A slower page could hurt every other metric |
| Guardrail | Bounce rate | Catches a design that confuses users |
| Guardrail | Complaints / support contacts per 1,000 users | Consumer Duty: customers must not be worse off |

*The public dataset only contains the primary metric. In a real test, the guardrails would be logged as well.*

## 3. Design

| Item | Plan |
|---|---|
| Unit of randomisation | **User** (each user always sees the same page) |
| Split | 50 / 50 |
| Baseline conversion | 12.0% |
| Minimum detectable effect (MDE) | **3% relative** (12.0% → 12.4%), the smallest lift worth the build cost |
| Significance level (α) | 0.05, two-sided |
| Power | 80% |
| Sample size | **129,081 users per group** |
| Traffic | ~12,600 users per day |
| Duration | **21 days (3 full weeks)**. 20 days meets the sample size, rounded up to whole weeks so every weekday is covered equally |

## 4. Before launch (QA)
- [ ] Confirm that every user in **control** sees the **old** page and every user in **treatment** sees the **new** page
- [ ] Confirm that a user can't be assigned to both groups (deduplicate by `user_id`)
- [ ] Run a 1-day A/A check: two identical groups should show no difference

## 5. During the test
- **Check SRM daily.** Stop and investigate if the overall split gives p < 0.001.
- **Don't stop early on a "win".** Simulation in this repo showed that daily peeking at p < 0.05 produces a false winner **22%** of the time.
  - Option A: one look only, at the end of day 21.
  - Option B: if daily looks are needed, a result only counts as significant if **p < 0.008**. This keeps the overall false-winner rate near 5%.

## 6. Analysis plan (fixed in advance)
1. Data-quality checks: wrong-page rows, duplicate users
2. SRM check, overall and daily
3. Two-proportion z-test, 95% confidence interval and relative lift
4. Bayesian readout: P(new better) and expected loss of each choice
5. £ impact per year (assuming £50 per conversion)
6. **Segments:** none are pre-registered. Any post-hoc segment results are exploratory only and need a **Holm correction**.
7. Novelty check: the effect by week

All of the above runs in one call: `src/ab_readout.py → ab_readout()`.

## 7. Decision rules (agreed before launch)

| Result | Decision |
|---|---|
| SRM alarm (p < 0.001) | **Invalid.** Fix the assignment and rerun the test |
| Whole CI above 0, guardrails OK | **Ship** |
| Whole CI below 0 | **Don't ship** |
| CI includes 0 | **Keep the current page.** Retest only if a bigger change is planned, because chasing lifts below the MDE isn't worth the traffic |
| Any guardrail significantly worse | **Don't ship**, whatever the primary metric shows |

## 8. Lessons from the real test

| Plan says | What actually happened |
|---|---|
| QA: no user in both groups | **3,893 users saw both pages.** An assignment bug that should have been caught before launch |
| Fixed duration of 21 days | The test ran for 23 days. ✅ Long enough |
| SRM check | Split was 50.006% (p = 0.95). ✅ Healthy every day |
| Decision rule | CI −0.39 to +0.08 pp, which includes 0, so **keep the current page** |
| Post-hoc segments | 4 of 31 looked significant and 0 survived Holm correction. ✅ Correctly ignored |
