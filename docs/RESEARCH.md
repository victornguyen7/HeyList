# HeyList — Research on the problem

Published numbers on the problem HeyList solves, for the Impact section of the Devpost description and the demo video ([SUBMISSION.md](SUBMISSION.md)). Collected 2026-10-31 from a web search.

**None of this shows that HeyList fixes the problem.** It shows the problem is real. Only tests with real groups can show the rest; none have been run yet ([ROADMAP.md](ROADMAP.md), Validation).

Most of these are surveys paid for by companies that sell something related (banks, payment apps, AI and retail vendors). Name the source whenever a number is quoted, and quote who was asked.

## How far each number was checked

| Label | Meaning |
|---|---|
| **Checked** | Read on the publisher's own page, including who was asked |
| **Reported** | Read in a news article about the survey, not the original |
| **Excerpt** | Seen only in a search result excerpt; the page itself was not read. Read the original before quoting |

## The problem: group money causes real damage

Safe to quote.

| Finding | Who was asked | Source | Checked | HeyList feature |
|---|---|---|---|---|
| **82%** would pay more than their fair share to avoid a money conflict (Gen Z 90%, millennials 86%) | US adults who took a group trip in the past 5 years, from a poll of 2,067 adults (±2.7) | [Harris Poll for CIT Bank, 14–18 May 2026](https://newsroom.firstcitizens.com/2026-06-23-82-of-Group-Travelers-Will-Pay-a-Peace-Tax-to-Avoid-Money-Arguments,-CIT-Bank-Survey-Finds) | Checked | Settle up: code does the asking and the math |
| **45%** have had financial conflict or discomfort on a trip (Gen Z 72%, millennials 54%) | Same | Same | Checked | The main problem |
| **61%** spent beyond their budget because of social pressure (Gen Z 80%, millennials 76%) | Same | Same | Checked | Budget on the starting list |
| **54%** of US adults have taken a group trip in the past 5 years | All US adults in the poll | Same | Checked | Size of the audience |
| **76%** weren't fully repaid after fronting money for a group expense | Gen Z who fronted a group expense, from a survey of 1,000 Americans | [Accelerant Research for Early Warning Services (owner of Zelle), May–June 2026](https://www.zelle.com/press-releases/new-zelle-research-group-chat-lit-settling-another-story) | Checked | Settle up and reminders |
| **33%** say settling shared expenses causes stress or anxiety | Gen Z, same survey | Same | Checked | Reminders |
| **20%** cancelled plans, or muted or ignored group chats, to avoid repaying | Gen Z, same survey | Same | Checked | Reminders |
| **Only 1 in 4** friend groups set a budget upfront | 700+ US adults who traveled overnight with friends in the past 5 years | [Experian, June 2025](https://www.experian.com/blogs/ask-experian/survey-financial-stress-of-traveling-with-friends/) | Checked | Budget in the one-sentence list |
| **35%** of millennials name different budget ranges as their biggest challenge | Millennials, same survey | Same | Checked | Budget on the starting list |
| **Average of $926 owed**; **32% of Gen Z** (15% of boomers) hesitate to ask for it back | 2,475 US adults (±1.97) | [YouGov for PayPal, 25–27 June 2024](https://newsroom.paypal-corp.com/2024-07-24-Owed-Money-Youre-Not-Alone-Heres-How-to-Ask-For-It-Back-Politely) | Checked | PayPal's own data; see the warning on averages below |

Experian's method note describes its sample as drawn from its consumer credit database and says little else about how people were recruited.

## The AI side: people won't let agents buy for them yet

Supports the design: the AI suggests, a person approves, PayPal confirms.

| Finding | Who was asked | Source | Checked |
|---|---|---|---|
| **5%** would trust an AI platform to process an agent's payment; **41%** trust none of the options tested; banks lead the named options at 17%, digital wallets 14% | 1,007 US consumers (field dates not given) | [Wildfire Systems, Oct 2026](https://www.wildfire-corp.com/blog/survey-agentic-commerce-payment-trust-problem) | Checked |
| **29%** are very comfortable with an agent buying something under $20; **6%** at $500 or more | Same | Same | Checked |
| **9%** would let an agent start and complete purchases within set limits; **12%** are open to agents deciding on their own at the payment stage | 25,590 consumers in 16 countries | [Accenture 2026 Consumer Pulse, via AI News](https://www.artificialintelligence-news.com/news/ai-shopping-agents-consumer-trust-accenture-report/) | Reported |
| **11%** at most would let AI make purchases, even for low-stakes items; **31%** would let it narrow choices for household supplies, 28% for personal electronics | 322 US consumers, January 2026 (a small sample) | [Gartner, 27 May 2026](https://www.gartner.com/en/newsroom/press-releases/2026-05-27-gartner-survey-finds-consumers-want-ai-shopping-help-but-not-ai-purchase-decisions) | Excerpt: Gartner and Business Wire both refused the fetch |

## Academic research

Backs up the problem in general. None of it tests a product like HeyList.

| Paper | Finding | Checked |
|---|---|---|
| [Daminger, "The Cognitive Dimension of Household Labor", *American Sociological Review* 84(4), 2019](https://inequality.hks.harvard.edu/publications/cognitive-dimension-household-labor) | 70 interviews with members of 35 couples. Tasks like shopping include hidden work: anticipating needs, identifying options, deciding and monitoring. Studies couples at home, so use it as a framing idea, not as evidence about friend groups | Excerpt of the abstract |
| ["Lend to a friend, lose a friend?", *Acta Psychologica*, 2026](https://www.sciencedirect.com/science/article/pii/S000169182501340X) | 384 people who had borrowed from peers. Shame lowers willingness to borrow and worsens repayment; guilt predicts better repayment | Excerpt: the page refused the fetch |
| [Angulo, "Friendship fallout and bailout backlash", *Journal of Consumer Psychology*, 2024](https://anderson-review.ucla.edu/wp-content/uploads/2024/08/Angulo-The-psychology-of-borrowing-and-lending.pdf) | Lenders feel they deserve more oversight when a borrower spends on non-essentials | Excerpt: the PDF could not be read |
| [Yu and Jaenicke, "Estimating Food Waste as Household Production Inefficiency", *American Journal of Agricultural Economics* 102(2), 2020](https://pure.psu.edu/en/publications/estimating-food-waste-as-household-production-inefficiency/) | About 4,000 US households waste 31.9% of the food they acquire. [Penn State's coverage](https://www.futurity.org/?p=2262612) says households using a shopping list waste less, but the abstract doesn't mention it. Off the main story; only for everyday grocery lists | Excerpt |

**Gap:** no peer-reviewed study was found on whether reminders or payment apps reduce the awkwardness of asking for money back.

## Do not quote yet

| Claim | Why not |
|---|---|
| **46%** of adults had tension or a "ruined vibe" on a group trip because of money (PayPal, 2,001 US adults, 2026) | Would be ideal, but found only in [a second-hand summary](https://www.zetik.com/news/article/story_id-p008-217841) of a New York Times article of 22 Sep. Find the original first |
| **55%** of those not fully repaid say it caused tension or hurt a relationship; **47%** went into debt (Zelle) | The [release](https://www.zelle.com/press-releases/new-zelle-research-group-chat-lit-settling-another-story) doesn't state clearly who was asked. [USA Today](https://finance.yahoo.com/small-business/articles/gen-z-taking-group-trips-120129876.html) reads the 55% as Gen Z who weren't fully repaid |
| "Over half argued about money" and "1 in 5 ended a friendship" (Experian) | Only Gen Z and millennials who travel with friends, with no exact percentage. Zelle's 14% (Gen Z) and 19% (millennials), and CIT's 22% (Gen Z travelers), ask different questions, so the numbers don't line up. Never quote these as "1 in 5 people" |
| **$926** owed, as a cost of group trips | It's an average across all debts, not just trips, and a few large debts can inflate an average. In [LendingTree's 2021 survey](https://lendingtree.com/2021/11/friend-or-family-owes-money-survey) the median was $400 and the average $8,170 |
| **68%** bought food they already had at home; **62%** missed items thinking they had them ([Tesco, UK, 2022](https://www.grocerygazette.co.uk/2022/11/09/tesco-reduce-food-waste/)); **88%** bought duplicates ([Hisense, UK](https://britbrief.co.uk/business/consumers/88-of-brits-waste-money-on-duplicate-groceries.html)) | About forgetting what's at home, not about groups buying the same thing. No data was found on group double-buying, so show that feature in the demo without a statistic |
| **More than 2 in 5** would stop using agents after one mistake ([Forbes, Oct 2026](https://www.forbes.com/sites/jordanmckee/2026/10/01/agentic-commerce-has-a-consumer-trust-problem/)) | Excerpt only; the page refused the fetch |
| Consumers give AI more authority when they set the limits; "trust no company" fell from 47% to 17% ([Riskified, 5,100 consumers, 2026](https://www.riskified.com/press/agentic-commerce-pulse-consumer-survey-november-2026/)) | Excerpt only; the page refused the fetch |
| **35%** want a human to review before an agent buys; 44% of boomers ([RTB House, 1,800+ people in 4 countries](https://chainstoreage.com/rtb-house-consumer-trust-agentic-ai-grows)) | Excerpt only; the page refused the fetch. Worth checking: it's the closest match to HeyList's approval step |
| **24%** trust agents with routine purchases ([Forrester](https://www.forrester.com/report/many-us-consumers-believe-in-agentic-commerce-but-few-trust-it-to-make-purchases/RES188737)) | Excerpt only, from a March 2025 survey, so older than the rest |
| **14%** have used an AI shopping assistant; **41%** have no trust in them ([YouGov, via Retail Dive](https://www.retaildive.com/news/ai-retail-shopping-assistants-consumer-trust/753687/)) | Excerpt only, and the date wasn't confirmed. The search also suggested "65% trust AI to compare prices, 14% to place orders", which could not be confirmed anywhere |
| **36%** have tried AI shopping tools; **56%** trust an agent's recommendation ([Harris Poll for Quad, 2,180 adults, Feb 2026](https://www.quad.com/newsroom/americans-say-they-would-lose-trust-in-ai-shopping-if-results-were-sponsored)) | Excerpt only, and the 56% statement was cut off |
| **44.7%** distanced themselves from a friend over money; **52.1%** argued (Self Financial, 1,001 US adults) | Excerpt of a second-hand report, and about friendship in general |
| **71%** have lent to friends and not been repaid; asking for repayment is the second most uncomfortable situation ([Bank of America, via Refinery29](https://www.refinery29.com/en-us/bank-of-america-study-friendship-money)) | Excerpt only, and the date wasn't confirmed |
| **41%** lent to a loved one in the past year, 27% regret it, 62% have been paid back ([LendingTree, 2020](https://www.lendingtree.com/2020/12/31-of-americans-would-rather-go-into-debt-than-borrow-from-loved-ones)); **31%** are owed money (LendingTree, 2021) | Excerpt only, old, and about loans in general |
| **60%** have lent cash expecting repayment; 46% of them had a bad outcome ([Bankrate, 2,490 adults, 2019](https://www.bankrate.com/finance/credit-cards/lending-money-survey-2019)) | Excerpt only, old, and about loans in general |
| **42%** of lenders weren't repaid ([CreditCards.com, via AARP](https://www.aarp.org/money/retirement/giving-money-to-family/)); **66%** ([CouponCodesPro, same page](https://www.aarp.org/money/retirement/giving-money-to-family/)) | Excerpt only. Non-repayment figures range from about 38% to 66% by wording; the CouponCodesPro source couldn't be identified |
| With a best friend, people are happier paying the whole bill than splitting it ([The Conversation](https://theconversation.com/time-to-ditch-splitting-the-bill-shouting-a-close-friend-could-actually-make-you-happier-261557); [Barton seminar, ANU](https://rsm.anu.edu.au/events/research-seminar-series-dr-belinda-barton)) | Excerpt only. It also cuts against automatic even splits between close friends |
| Uncertainty about who pays harms later social interaction ([diners study, via MetaTOC](https://metatoc.com/papers/75513-when-sharing-is-not-caring-does-un-certainty-about-bill-payment-method-lead-diners-to-consume-more-and-spend-more-money)) | Excerpt only; authors and journal weren't shown |

## How to use it

Two numbers at most in the video. Show the source on screen.

> "In a Harris Poll for CIT Bank, 82% of group travelers said they'd overpay rather than risk an argument about money. And consumers don't trust AI with their money yet: in Accenture's survey of 25,590 people, 9% would let an agent complete a purchase, even within set limits. So HeyList's AI suggests, your group approves, and PayPal confirms what really got paid."

On screen: "Harris Poll for CIT Bank, 2026" and "Accenture Consumer Pulse, 2026". Gartner's 11% is the alternative once its release has been read. Put the tables above in the Devpost Impact section, then add the results of the group tests next to them.

**Expect this objection:** Experian notes that younger travelers already use apps like Splitwise and Venmo, and low trust in AI buying can also mean the market isn't ready. The answer: those apps record what people type in, while HeyList ties each item to a PayPal payment or a receipt. And the agent doesn't need people's full trust, because a person approves every purchase.
