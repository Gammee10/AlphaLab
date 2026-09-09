# Project Brief — Trading Research & Backtesting Platform

## 1. Project Overview

Build a research and experimentation platform for retail traders.

The platform should allow a trader to take a trading idea or strategy, turn it into a structured and executable strategy, run a realistic backtest on historical market data, inspect the results, and iteratively modify and test the strategy.

The goal is to make systematic trading research significantly easier.

Instead of:

> "I have an idea → spend hours coding the strategy → build a backtesting script → debug it → find out the idea doesn't work."

The platform should enable:

> "I have an idea → configure or modify a strategy template → backtest it → understand the results → modify it → test again."

The platform should function as a **research environment**, not as a live trading platform in the initial version.

---

# 2. Problem

Retail traders often have ideas they want to test:

- "What if I only trade with the trend?"
- "What if I enter after a liquidity sweep?"
- "Does this strategy work better during high volatility?"
- "What happens if I change my stop loss?"
- "Does this strategy actually have an edge?"
- "Does this strategy still work after accounting for fees and slippage?"
- "Does it work across different market conditions?"
- "What happens if I change the timeframe?"
- "Which parameters have the biggest impact on performance?"

Testing these ideas often requires significant technical knowledge.

A trader may need to:

1. Obtain historical data.
2. Clean and prepare the data.
3. Write strategy logic.
4. Build a backtesting engine or learn a backtesting framework.
5. Implement position sizing.
6. Implement entry and exit rules.
7. Model fees and slippage.
8. Handle stop losses and take profits.
9. Run the backtest.
10. Analyze performance.
11. Modify the strategy.
12. Repeat the entire process.

This creates a large barrier between **having a trading idea** and **actually researching whether the idea has merit**.

The platform should reduce this friction.

---

# 3. Vision

Create a platform where a retail trader can experiment with systematic trading ideas without needing to build the entire research infrastructure themselves.

The central experience should be:

**Idea → Build → Backtest → Analyze → Modify → Backtest again**

The platform should make iteration cheap, fast, and reproducible.

A trader should be able to compare different versions of a strategy and understand how changes affect its behavior.

---

# 4. Target User

The primary target user is the **retail trader**.

The initial product does not need to target professional quantitative researchers, hedge funds, institutional traders, or large trading firms.

However, the underlying system should ideally be designed cleanly enough that more advanced users could eventually use it.

The initial experience should prioritize:

- Ease of use
- Low technical barrier
- Fast experimentation
- Clear results
- Reproducibility
- Realistic simulation
- Strategy iteration

---

# 5. Core Product Loop

The primary user workflow should be:

### Step 1 — Start with an idea

The user describes or selects a trading strategy.

Examples:

- Trend-following strategy
- Breakout strategy
- Mean-reversion strategy
- Volatility strategy
- Liquidity-based strategy
- Moving-average strategy
- Momentum strategy
- Range strategy

The user should not necessarily need to know how to implement the strategy in code.

---

### Step 2 — Build the strategy

The platform should provide reusable strategy templates for common strategy categories.

Rather than forcing the AI to generate an entire trading system from scratch every time, the platform should provide structured templates/components that represent common strategy patterns.

Examples could include:

- Trend
- Momentum
- Mean reversion
- Breakout
- Volatility
- Liquidity
- Support/resistance
- Moving averages
- ATR-based logic
- Time/session filters
- Risk management rules

The exact template system should be determined during architecture/design.

The important requirement is:

> The system should favor reusable, structured strategy building blocks over generating every strategy entirely from scratch.

---

### Step 3 — Configure or modify the strategy

The user should be able to modify the strategy according to their requirements.

For example:

> "Only enter long trades when the 50 EMA is above the 200 EMA."

or:

> "Change the stop loss from 1 ATR to 1.5 ATR."

or:

> "Only trade between the London and New York sessions."

or:

> "Add a volatility filter."

The platform's AI should assist with these modifications.

---

### Step 4 — Backtest

The user should be able to initiate a backtest with minimal friction.

Ideally, the experience should approach:

**Configure strategy → One-click Backtest**

The system should handle the underlying work required to construct and execute the backtest.

The user should not need to manually create a separate backtesting program for every strategy.

---

# 6. Realistic Backtesting

Realistic simulation is a core product requirement.

This should not be a simplistic backtester that assumes:

> "Signal happened → magically enter at the exact desired price → magically exit there."

The backtesting engine should aim to model realistic trading conditions.

Depending on the selected market and available data, the system should consider concepts such as:

- Trading fees/commissions
- Spread
- Slippage
- Position sizing
- Account balance/equity
- Leverage
- Margin where applicable
- Stop-loss execution
- Take-profit execution
- Position entry and exit
- Partial exits where supported
- Multiple simultaneous positions where supported
- Order types where applicable
- Trading session restrictions
- Market hours
- Capital constraints
- Risk-per-trade
- Maximum position size
- Drawdown
- Intrabar execution considerations

The system must also actively avoid common backtesting errors such as:

- Lookahead bias
- Future-data leakage
- Incorrect indicator calculation
- Incorrect order sequencing
- Unrealistic fills
- Incorrect handling of stops and targets
- Using information that would not have been available at the time of the trade

The architecture phase should determine the appropriate implementation and execution model.

The goal is not to promise that historical backtests perfectly predict future performance.

The goal is to make the simulation sufficiently realistic that the results are useful for research.

---

# 7. Backtest Results

After a backtest, the user should be able to understand how the strategy performed.

The platform should provide meaningful performance and risk information rather than only showing total profit.

Potential metrics include:

- Total return
- Net profit/loss
- Win rate
- Loss rate
- Profit factor
- Expectancy
- Average win
- Average loss
- Risk/reward characteristics
- Maximum drawdown
- Average drawdown
- Number of trades
- Consecutive wins/losses
- Sharpe ratio or similar risk-adjusted metrics
- Equity curve
- Drawdown curve
- Trade distribution
- Monthly/weekly performance
- Performance by market/session/time period

The exact metrics and visualization system should be determined during the architecture/specification phase.

---

# 8. Research & Experimentation

Backtesting should not be treated as a single "did it make money?" calculation.

The platform should help the trader investigate the behavior of a strategy.

Useful research capabilities may include:

### Parameter experimentation

Example:

- Stop loss: 0.5 ATR
- Stop loss: 1 ATR
- Stop loss: 1.5 ATR
- Stop loss: 2 ATR

Then compare the resulting performance.

### Timeframe comparison

For example:

- 5 minute
- 15 minute
- 1 hour
- 4 hour

### Market comparison

For example:

- EUR/USD
- GBP/USD
- XAU/USD
- BTC/USD

### Time-period comparison

For example:

- 2020–2021
- 2022
- 2023
- 2024
- 2025

### Market-condition analysis

Where possible, investigate performance during:

- High volatility
- Low volatility
- Trending markets
- Ranging markets
- Different sessions
- Different periods

The system should make it easier to determine whether a strategy has a robust edge or whether its performance depends heavily on a particular period or parameter.

---

# 9. AI Capabilities

AI is an important part of the product, but it should not replace the underlying research infrastructure.

The AI should act as a **research and strategy-development assistant**.

### 9.1 Strategy generation

The user should be able to describe an idea in natural language.

Example:

> "Create a trend-following strategy that enters after a pullback to the 20 EMA when the 50 EMA is above the 200 EMA."

The AI should translate the idea into the platform's structured strategy representation.

---

### 9.2 Strategy modification

The user should be able to ask the AI to modify an existing strategy.

Examples:

> "Add an ATR volatility filter."

> "Only trade during London and New York."

> "Change the risk per trade to 0.5%."

> "Remove the RSI condition."

The AI should modify the existing strategy rather than unnecessarily rebuilding the entire strategy from scratch.

---

### 9.3 Strategy explanation

The AI should be able to explain the strategy in understandable terms.

For example:

- What conditions trigger an entry?
- What conditions trigger an exit?
- How is position size calculated?
- What filters are being used?
- What assumptions does the strategy make?

---

### 9.4 Backtest result analysis

The AI should help interpret results.

For example:

> "Why does this strategy have a high win rate but poor profitability?"

or:

> "What appears to be the biggest weakness of this strategy?"

or:

> "Compare these two backtests."

The AI should base its analysis on actual backtest data rather than inventing conclusions.

---

### 9.5 Strategy debugging

If a strategy cannot be executed or produces unexpected behavior, the AI should help identify the problem.

However, the AI should not silently change the strategy's intended behavior merely to make the backtest run.

---

# 10. Strategy Templates

A major product concept is the use of **strategy templates**.

The platform should provide reusable templates for common trading concepts.

Instead of:

> AI generates 500 lines of strategy code from scratch.

The preferred model is closer to:

> Select a strategy/template → configure its components → AI modifies the structured strategy → generate/execute the backtest.

This should improve:

- Consistency
- Reliability
- Maintainability
- Explainability
- AI modification accuracy
- Development speed
- Reproducibility

The exact internal representation of strategies is an architectural decision and should not be predetermined by this brief.

---

# 11. Strategy Reproducibility

A backtest should be reproducible.

The system should preserve enough information to understand exactly what was tested.

A research result should be associated with things such as:

- Strategy version
- Strategy parameters
- Historical dataset/version
- Instrument
- Timeframe
- Backtest period
- Execution assumptions
- Fees
- Slippage
- Starting capital
- Position sizing/risk configuration
- Other relevant configuration

Changing a strategy should create a distinguishable version rather than silently overwriting previous research.

The user should be able to compare strategy versions.

---

# 12. Historical Market Data

The platform requires historical market data to perform backtests.

The architecture phase should determine:

- Supported markets
- Supported instruments
- Supported timeframes
- Data providers
- Data storage model
- Data ingestion
- Data normalization
- Data quality validation
- Handling of missing data
- Dataset versioning
- Data licensing considerations

The initial implementation should not attempt to support every market and data source.

A focused initial scope is preferable.

---

# 13. Research Safety / Integrity

The platform is intended for research and experimentation.

It should not present backtest results as proof that a strategy will be profitable in live trading.

The product should clearly distinguish:

**Historical simulation ≠ guaranteed future performance.**

The system should prioritize research integrity by making assumptions visible and avoiding misleading performance calculations.

Where appropriate, the platform should encourage practices such as:

- Out-of-sample testing
- Walk-forward testing
- Avoiding overfitting
- Testing across multiple periods
- Testing across different market conditions
- Separating strategy development data from evaluation data

These capabilities may be introduced incrementally.

---

# 14. Initial Product Boundary

The initial version should focus on:

1. Strategy creation
2. Strategy templates
3. Strategy modification
4. Historical market data
5. Realistic backtesting
6. Backtest results
7. Basic research/experimentation
8. AI-assisted strategy development
9. Strategy versioning/reproducibility
10. Comparing backtest results

The first version should **not** attempt to become a complete trading ecosystem.

---

# 15. Explicit Non-Goals for the Initial Version

The initial version does not need to provide:

- Live trading
- Broker execution
- Automatic real-money trading
- Portfolio management
- Social trading
- Copy trading
- A trading community
- A marketplace for strategies
- Institutional-grade infrastructure
- Every possible financial market
- Every possible technical indicator
- Every possible strategy type
- Fully autonomous trading decisions

These may be future possibilities, but they should not unnecessarily expand the initial product.

---

# 16. Product Principles

The system should follow these principles:

### Research first

The primary purpose is to help users research trading ideas.

### Realistic simulation

Backtests should model important real-world trading constraints rather than producing artificially attractive results.

### Reproducibility

A user should be able to understand and reproduce what generated a result.

### Iteration

Changing and retesting a strategy should be easy.

### Structured strategies

Prefer structured, reusable strategy components/templates over arbitrary generated code wherever practical.

### AI as an assistant

AI should accelerate strategy development and research, not replace deterministic systems that should remain reliable and testable.

### Transparency

The user should understand what was tested and under what assumptions.

### Avoid unnecessary complexity

The initial system should solve the core research problem well rather than attempting to build every possible trading feature.

---

# 17. Example User Journey

A user wants to test the following idea:

> "I want to trade EUR/USD on the 15-minute timeframe. I want to trade in the direction of the larger trend, enter after a pullback, risk 0.5% per trade, and use a 2:1 reward-to-risk target."

The user could:

1. Select a trend-following template.
2. Select EUR/USD.
3. Select the 15-minute timeframe.
4. Configure the trend conditions.
5. Configure the pullback entry.
6. Configure risk at 0.5%.
7. Configure the 2:1 target.
8. Select a historical period.
9. Click **Backtest**.
10. Inspect the results.
11. Ask the AI to analyze the strategy.
12. Ask the AI to add a volatility filter.
13. Run another backtest.
14. Compare the two strategy versions.
15. Continue iterating.

The entire workflow should feel like a research environment rather than a programming project.

---

# 18. What Makes This Product Different

The product should not simply be:

> "ChatGPT for trading strategies."

Nor should it simply be:

> "Another backtesting library with a UI."

The intended combination is:

**Structured strategy building + reusable templates + realistic backtesting + rapid experimentation + AI assistance.**

The AI should sit on top of a reliable deterministic research system.

The platform should make it dramatically easier to move from:

**Trading idea**

to

**Testable strategy**

to

**Backtest**

to

**Research insight**

to

**Improved strategy**

---

# 19. Architecture Phase Instructions

The next phase of this project is architecture and system design.

The architecture agent should **not begin implementation immediately**.

First, it should analyze this project brief and produce an architecture that can support the intended product.

The architecture phase should:

1. Identify the major domains and system boundaries.
2. Identify the core entities and their relationships.
3. Define the strategy representation.
4. Define the strategy-template system.
5. Design the backtesting/execution engine boundary.
6. Design the historical-data subsystem.
7. Define how strategies are versioned and reproduced.
8. Define the AI integration boundary.
9. Define the research/result model.
10. Define how backtests are executed.
11. Define how users compare experiments.
12. Identify important technical risks.
13. Identify areas where realistic simulation is difficult.
14. Identify potential sources of lookahead bias and data leakage.
15. Evaluate relevant architectural alternatives before selecting an approach.
16. Define clear boundaries between deterministic trading logic and AI-generated/modifiable logic.
17. Produce implementation-ready specifications after the architecture is established.

The architecture agent should explicitly challenge assumptions in this brief where necessary.

It should not blindly implement every idea described here.

If a requirement creates significant architectural problems, the agent should identify the problem, explain the trade-offs, and recommend an alternative.

---

# 20. Important Architectural Constraint

The platform should not depend on an LLM being correct for core financial calculations.

Core components such as:

- Order execution simulation
- Position sizing
- P&L calculation
- Fees
- Slippage
- Equity calculation
- Drawdown
- Performance metrics
- Historical data processing
- Strategy execution

should be deterministic and testable.

AI may **define, modify, explain, or analyze** strategy behavior, but the actual backtest should be performed by deterministic software.

---

# 21. Expected Development Process

The project should proceed through these phases:

### Phase 1 — Product Understanding

Understand and challenge this brief.

### Phase 2 — Architecture

Design the overall architecture and evaluate alternatives.

### Phase 3 — Specifications

Produce sufficiently detailed specifications for implementation.

### Phase 4 — Implementation Planning

Break the system into implementable components and milestones.

### Phase 5 — Implementation

Build the system according to the approved architecture and specifications.

### Phase 6 — Validation

Test the system thoroughly, especially the backtesting engine and strategy execution.

The architecture and specification phases should be completed before substantial implementation begins.

---

# 22. Final Product Goal

The ultimate goal is to create a platform where a retail trader can say:

> "I have an idea for a trading strategy. Let me test it."

and go from that idea to a meaningful, reproducible backtest with as little unnecessary technical work as possible.

The platform should make **researching a trading idea easier than blindly implementing it and risking real money.**