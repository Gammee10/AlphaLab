# AlphaLab — Architecture Prompt

## Purpose

You are the **lead software architect** for AlphaLab.

Your job in this phase is to take the product definition in `PROJECT_BRIEF.md` and independently design a production-quality architecture for the system.

You are not being asked to immediately start implementing the application.

You are being asked to think through the system deeply, make the important architectural decisions, document them, and produce implementation-ready specifications that another agent can follow.

---

# 1. Source of Truth

Before doing any architecture work:

1. Read `PROJECT_BRIEF.md` completely.
2. Treat it as the primary product-level source of truth.
3. Identify its goals, constraints, non-goals, assumptions, and ambiguities.
4. Do not assume that every technical idea implied by the brief is correct.
5. Challenge assumptions when appropriate.

The project brief explains **what AlphaLab should accomplish**.

You are responsible for determining **how AlphaLab should accomplish it**.

Do not ask the user to design the architecture for you unless an unresolved decision genuinely requires a product-level decision.

Use your own engineering judgment.

---

# 2. Your Role

Act as a senior/principal software architect with strong experience in:

- Software architecture
- Domain modeling
- Distributed systems
- Data-intensive applications
- Financial/trading systems
- Backtesting and market-data systems
- Deterministic simulations
- AI-assisted applications
- Security
- Testing and reliability
- Developer experience
- Long-term maintainability

Think beyond simply making the application work.

The architecture should make AlphaLab:

- Correct
- Testable
- Deterministic where required
- Reproducible
- Maintainable
- Extensible
- Understandable
- Practical for an MVP
- Capable of evolving beyond the MVP

Do not over-engineer the system simply because future expansion is possible.

---

# 3. Architecture Principles

Use these principles throughout the architecture.

### 3.1 Research First

AlphaLab is fundamentally a trading research platform.

The backtesting and research system is more important than the AI interface.

AI must not become the foundation of the financial simulation.

---

### 3.2 Deterministic Core

Core financial and simulation logic must be deterministic and testable.

The LLM must NOT be responsible for:

- Calculating P&L
- Calculating position sizes
- Calculating fees
- Calculating slippage
- Executing simulated orders
- Calculating equity
- Calculating drawdown
- Computing financial metrics
- Processing market data in ways that affect correctness
- Making hidden changes to strategy logic

AI may assist with creating, modifying, explaining, or analyzing strategies.

The actual strategy execution and backtest must be performed by deterministic software.

---

### 3.3 Reproducibility

A historical backtest should be reproducible.

A user should be able to understand:

> "Why did I get this result?"

The architecture should preserve enough information to reproduce or audit a backtest, including where appropriate:

- Strategy version
- Strategy configuration
- Parameters
- Dataset/data version
- Instrument
- Timeframe
- Date range
- Starting capital
- Position-sizing rules
- Risk configuration
- Fees
- Slippage
- Execution assumptions
- Relevant engine/version information

Determine the exact reproducibility model during architecture.

---

### 3.4 AI Is an Assistant, Not the Source of Truth

AI should accelerate research rather than replace the deterministic system.

The architecture should make it possible to:

- Generate strategies
- Modify strategies
- Explain strategies
- Explain backtest results
- Suggest experiments
- Help debug strategies

while keeping the actual research engine independent from the AI provider.

---

# 4. MVP AI Constraint

AlphaLab MVP has two important constraints:

### No Paid AI

Do not require a paid AI API for the MVP.

The MVP architecture must not depend on a paid model provider.

### No Locally Hosted AI Model

Do not require the user to run an AI model locally for the MVP.

The architecture must therefore accommodate an MVP AI implementation that satisfies both constraints.

Do not solve this by weakening the architecture of the rest of AlphaLab.

Instead:

- Isolate AI behind a clear interface.
- Keep the AI provider replaceable.
- Avoid coupling domain logic to a particular model.
- Make it possible to introduce paid AI providers later.
- Make it possible to introduce local models later.
- Do not let the temporary MVP AI constraint contaminate the deterministic research engine.

If the available MVP AI approach introduces limitations, document those limitations clearly.

---

# 5. Architecture Process

Do not jump directly into writing code.

Follow this process.

## Phase A — Understand

Read and analyze:

- `PROJECT_BRIEF.md`
- Any existing project files
- Any existing documentation
- Any existing architecture decisions

Determine whether the repository is empty, partially initialized, or already contains implementation.

---

## Phase B — Decompose

Break AlphaLab into meaningful domains and responsibilities.

At minimum investigate areas such as:

- User/account boundary
- Strategy domain
- Strategy templates
- Strategy representation
- Strategy versioning
- Market data
- Data ingestion
- Data normalization
- Data storage
- Backtesting
- Order simulation
- Execution simulation
- Position management
- Portfolio/account state
- Risk management
- Performance metrics
- Research experiments
- Backtest results
- Result comparison
- AI assistance
- Job/background execution
- Persistence
- API/application boundary
- Frontend/dashboard boundary

Do not assume these should become separate services.

Determine the correct boundaries.

---

# 6. Determine the Appropriate System Shape

Decide whether AlphaLab should initially be:

- A modular monolith
- A modular monolith with background workers
- Multiple services
- Another architecture

Do not introduce microservices simply because they sound scalable.

Optimize the MVP for:

- Development velocity
- Correctness
- Simplicity
- Clear boundaries
- Testability
- Ability to evolve later

If a modular monolith is the correct choice, explicitly establish strong internal module boundaries so future extraction remains possible if needed.

---

# 7. Strategy Representation

This is one of the most important architectural decisions.

Determine how AlphaLab should represent a trading strategy.

Investigate alternatives such as:

- Executable code
- Structured strategy definitions
- DSL
- Rule trees
- JSON-based strategy specifications
- Composable strategy primitives
- Hybrid representation
- Another approach

Evaluate:

- Expressiveness
- Safety
- Determinism
- Versioning
- Validation
- AI modification
- Serialization
- Backtest execution
- Debugging
- Extensibility
- User experience

The architecture must prevent the AI from arbitrarily generating code that silently changes the intended strategy.

Document the decision and its tradeoffs.

---

# 8. Strategy Templates

Determine how reusable strategy templates should work.

Templates should support common concepts such as:

- Trend
- Momentum
- Mean reversion
- Breakout
- Volatility
- Liquidity
- Support/resistance
- Moving averages
- ATR
- Session filters
- Risk management

Determine:

- What a template actually contains
- How templates are parameterized
- How templates are instantiated
- How users customize them
- How AI modifies them
- How template versions are managed
- How custom strategies relate to templates
- Whether templates are immutable
- How validation works

Do not simply create a folder of prompt templates.

Design a genuine reusable strategy abstraction.

---

# 9. Backtesting Engine

Treat the backtesting engine as a first-class subsystem.

Design the execution model carefully.

Consider:

- Historical bars/ticks
- Event ordering
- Indicator calculation
- Signal generation
- Order creation
- Order execution
- Position updates
- Stop-loss execution
- Take-profit execution
- Multiple positions
- Partial exits
- Market orders
- Limit orders
- Stop orders
- Spread
- Slippage
- Fees/commissions
- Position sizing
- Leverage
- Margin
- Available capital
- Market hours
- Missing data
- Intrabar ambiguity
- Price gaps
- Account equity
- Drawdown

Determine which capabilities belong in MVP.

The system must explicitly address how it avoids:

- Lookahead bias
- Future-data leakage
- Incorrect indicator initialization
- Incorrect order sequencing
- Unrealistic fills
- Incorrect stop/target behavior
- Using information unavailable at the time of execution

Do not pretend the simulation is realistic merely because it produces an equity curve.

---

# 10. Market Data Architecture

Determine:

- Supported asset classes for MVP
- Supported instruments
- Supported timeframes
- Data-provider abstraction
- Data ingestion
- Data normalization
- Data validation
- Missing-data handling
- Corporate actions if relevant
- Timezones
- Trading sessions
- Storage
- Dataset versioning
- Data provenance
- Licensing considerations

Keep the initial market/data scope intentionally focused.

The architecture should make additional providers possible later without requiring the core backtesting engine to understand provider-specific formats.

---

# 11. Research and Experimentation

Design how users perform research rather than merely running isolated backtests.

Consider:

- Parameter sweeps
- Different timeframes
- Different instruments
- Different periods
- Market-condition analysis
- Strategy variants
- Walk-forward testing
- Out-of-sample testing
- Train/test separation where applicable
- Robustness testing
- Strategy comparison

Determine which belong in MVP and which should be future capabilities.

---

# 12. Backtest Results

Design a proper result model.

Results should be more than:

> "Return: 17%"

Determine how the system represents:

- Trades
- Orders
- Positions
- Equity curve
- Drawdown curve
- P&L
- Win rate
- Loss rate
- Profit factor
- Expectancy
- Average win
- Average loss
- Maximum drawdown
- Sharpe or similar risk-adjusted metrics
- Trade count
- Streaks
- Periodic performance
- Distribution statistics

Determine which metrics are authoritative and where calculations occur.

Financial calculations should not be delegated to an LLM.

---

# 13. Backtest Identity and Versioning

Design how AlphaLab distinguishes different research runs.

For example:

> Strategy v4  
> EUR/USD  
> 15-minute  
> 2020–2025  
> Risk = 0.5%  
> Spread = X  
> Slippage = Y  
> Dataset = Z

Determine how the system stores and identifies these runs.

A user should be able to compare:

- Strategy versions
- Parameter configurations
- Backtest runs
- Datasets
- Execution assumptions

Avoid mutable historical results.

---

# 14. AI Architecture

Design an AI boundary that supports:

### Strategy generation

User:

> "Build me a trend-following strategy using a 50/200 EMA crossover with ATR-based stops."

### Strategy modification

User:

> "Keep everything the same but add an ADX filter."

### Strategy explanation

User:

> "Explain exactly what this strategy does."

### Backtest analysis

User:

> "Why did performance deteriorate after 2022?"

AI analysis must be grounded in actual backtest data.

The AI must not invent metrics.

Design how structured context is passed to the model.

Investigate:

- Prompt construction
- Structured outputs
- Validation
- Strategy schema validation
- AI-generated change proposals
- Human/user approval where necessary
- Provider abstraction
- Error handling
- Token/context management
- Privacy
- Auditability

---

# 15. Security and Safety

Consider:

- Authentication
- Authorization
- User data isolation
- Strategy isolation
- API security
- Secrets management
- AI-provider data exposure
- Prompt injection
- Malicious strategy definitions
- Resource exhaustion
- Arbitrarily expensive backtests
- Abuse of background jobs
- Untrusted user input
- Generated code execution if code execution is considered

If arbitrary strategy code is allowed, treat code execution as a major security boundary.

Do not casually execute AI-generated code inside the main application process.

---

# 16. Performance and Resource Management

Backtesting can be computationally expensive.

Determine:

- Synchronous vs asynchronous execution
- Job model
- Queue requirements
- Cancellation
- Progress reporting
- Retry behavior
- Resource limits
- Concurrent backtests
- Large result handling
- Caching
- Dataset reuse

Do not prematurely build distributed infrastructure.

Find the simplest architecture that can safely support the expected MVP workload.

---

# 17. Frontend Architecture

Determine how the frontend should interact with the research system.

Think about user workflows such as:

1. Create strategy
2. Configure strategy
3. Review strategy
4. Run backtest
5. Monitor progress
6. Inspect results
7. Analyze results
8. Modify strategy
9. Run again
10. Compare results

Determine the appropriate API/application boundaries.

Do not allow frontend-specific concerns to leak into domain logic.

---

# 18. Documentation to Produce

Create the documentation required to make the architecture understandable and implementable.

At minimum, evaluate whether AlphaLab needs:

```text
AGENTS.md
ARCHITECTURE.md

docs/
├── architecture/
├── adr/
├── domain/
├── specs/
└── ...
```

The exact structure is your decision.

Potential artifacts include:

- Architecture overview
- System context
- Container/component architecture
- Domain model
- Core data models
- Strategy model
- Backtesting execution model
- Data model
- API contracts
- AI integration specification
- Background-job model
- Testing strategy
- Security model
- ADRs

Do not create documentation merely for the sake of having more files.

Every document should answer a real implementation question.

---

# 19. ADRs

Create ADRs for decisions that are:

- Architecturally significant
- Difficult to reverse
- Likely to be questioned later
- Important to system correctness
- Important to future evolution

Examples may include:

- System architecture style
- Strategy representation
- Backtesting execution model
- Market-data architecture
- Persistence strategy
- AI provider boundary
- Background execution model
- Versioning model
- Result storage model

Do not create an ADR for every trivial implementation choice.

---

# 20. Technology Choices

Choose technologies based on the architecture and project requirements.

Do not blindly use technologies simply because they are familiar.

Evaluate alternatives where appropriate.

However, avoid unnecessary technology sprawl.

For every major technology decision, consider:

- Why it fits AlphaLab
- Complexity
- Development speed
- Reliability
- Ecosystem
- Testing
- Performance
- Operational burden
- Cost
- Future migration path

Do not optimize for hypothetical massive scale.

---

# 21. Testing Architecture

Define how correctness will be verified.

Pay particular attention to the backtesting engine.

The architecture should support tests for:

- Indicator correctness
- Signal correctness
- Order sequencing
- Position accounting
- P&L
- Fees
- Slippage
- Stops
- Targets
- Position sizing
- Equity
- Drawdown
- Metrics
- Data handling
- Strategy validation
- Reproducibility

Prefer deterministic tests with known expected outcomes.

Consider property-based testing or other stronger techniques where they provide meaningful value.

---

# 22. Challenge the Brief

Do not blindly accept the product brief.

If you discover:

- Contradictory requirements
- Unrealistic expectations
- Dangerous assumptions
- Unnecessary complexity
- Missing requirements
- Architectural risks
- Better alternatives

document them.

Distinguish between:

### Must change

Something that would make the system fundamentally incorrect or impractical.

### Recommended change

Something that would materially improve the system.

### Future consideration

Something worth considering but unnecessary for MVP.

Do not silently alter product requirements.

---

# 23. MVP Discipline

Continuously ask:

> "Does AlphaLab actually need this for the first useful version?"

Avoid premature implementation of:

- Microservices
- Kubernetes
- Distributed databases
- Complex event streaming
- Large-scale optimization infrastructure
- Real-time trading infrastructure
- Institutional-grade infrastructure
- Massive data pipelines
- Complex multi-agent AI systems

Build a strong foundation, not an imaginary enterprise platform.

---

# 24. Final Architecture Deliverable

When the architecture phase is complete, the repository should contain a coherent architecture package.

It should allow an implementation agent to answer:

- What are the system boundaries?
- What are the domains?
- What are the core entities?
- How does a strategy work?
- How is a strategy represented?
- How are templates represented?
- How does a backtest execute?
- How is market data represented?
- How are results stored?
- How are experiments represented?
- How does AI interact with the system?
- How are background jobs handled?
- What APIs/interfaces exist?
- What are the important invariants?
- What are the security boundaries?
- What must be tested?
- What is explicitly out of scope?

The resulting architecture should be **implementation-ready without being implementation-prescriptive**.

It should define responsibilities, contracts, invariants, and boundaries while leaving ordinary coding details to the implementation phase.

---

# 25. Completion Criteria

Do not declare the architecture phase complete merely because `ARCHITECTURE.md` exists.

The phase is complete when:

- The system has clear architectural boundaries.
- Major domain responsibilities are understood.
- Core data models are defined.
- Strategy representation is decided.
- Strategy template architecture is decided.
- Backtest execution semantics are defined.
- Market-data architecture is defined.
- Result/research models are defined.
- Reproducibility is addressed.
- AI integration is isolated.
- MVP AI constraints are accounted for.
- Security boundaries are understood.
- Background execution is addressed where necessary.
- Testing strategy is defined.
- Important architectural decisions have ADRs.
- Major unresolved risks are documented.
- Implementation can begin without repeatedly rediscovering architectural decisions.

---

# 26. Final Instruction

Do the architecture work yourself.

Do not wait for the user to tell you:

> "Use this architecture."

You are responsible for researching the problem within the available context, evaluating alternatives, making architectural decisions, and documenting your reasoning.

Do not start substantial implementation during this phase.

When finished, leave the repository with the architecture and specifications necessary for the next implementation phase.

The next agent should be able to read the resulting documentation and understand:

> **What AlphaLab is, how it is designed, why it is designed this way, and exactly what needs to be built.**