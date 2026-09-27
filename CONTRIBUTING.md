# Contributing

Contributions are welcome.

Useful contributions include:

- compatibility fixes for newer Pi or Open WebUI releases;
- clearer installation instructions;
- bug fixes;
- tests;
- ports to additional agent harnesses;
- examples of bounded Fresh Worker prompts.

## Core contract

Please preserve the defining behaviour:

1. the worker starts in a genuinely new context/session;
2. parent conversation history is not silently copied;
3. the parent provides one explicit self-contained prompt;
4. the worker result is returned to the caller;
5. isolation behaviour is documented and inspectable.

A port may use different host APIs, but it should not call itself Fresh Worker if it simply continues the parent conversation under another label.

## Pull requests

Please include:

- what changed;
- which host/version you tested;
- how you verified context isolation;
- any new permissions or external calls introduced.
