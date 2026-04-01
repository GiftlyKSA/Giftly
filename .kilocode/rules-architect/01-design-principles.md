# Design Principles

- Prefer simple, low-dependency designs. Complexity must be justified.
- Define clear boundaries between components — each should have one reason to change.
- Design for failure: every integration point can fail. Make failure modes explicit.
- Avoid speculative generality — design for current requirements, not hypothetical future ones.

- Prefer stateless components where possible. Clearly define a single source of truth for data.
- Avoid shared mutable state across component boundaries.

- Define explicit interfaces between components. Do not leak internal implementation details.
- Inputs and outputs must be well-defined and validated.

- Minimize coupling between components. Prefer dependency injection over hard dependencies.
- High-level modules should not depend on low-level implementation details.

- Systems must be observable: include logging, metrics, or tracing at critical paths.
- Failures must be visible and easy to diagnose.

- Design for current scale, but document assumptions and potential bottlenecks.
- Optimize only when there is evidence or clear risk.

- External operations should be idempotent where possible.
- Define consistency expectations (strong vs eventual) when relevant.
- Handle retries safely and predictably.