# ⚓ AnchorTest

> **AI-Powered Test Case Generation Framework for HTTP Server Applications**

AnchorTest is an intelligent, LangGraph-powered testing framework that automatically generates, manages, and evolves test cases for HTTP server applications. By analyzing requirements and specification documents, AnchorTest produces structured test suites and keeps them in sync as your product evolves — phase by phase.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Test Case Types](#test-case-types)
- [Test Flow Types](#test-flow-types)
- [Tags System](#tags-system)
- [Phases](#phases)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [License](#license)

---

## Overview

AnchorTest bridges the gap between product documentation and test coverage. Feed it your requirements or spec document, and it produces a comprehensive, tagged suite of test cases for your HTTP server. As your specs evolve across development phases, AnchorTest intelligently **adds**, **modifies**, and **removes** test cases to keep your suite current — no manual triage required.

---

## Key Features

- 🧠 **LangGraph-Driven Orchestration** — multi-step reasoning pipeline to interpret specs and generate coherent test suites
- 📄 **Requirement-to-Test Generation** — converts raw requirements and spec documents into structured test cases
- 🔄 **Incremental Phase Updates** — subsequent spec updates trigger smart diff-based additions, modifications, and deletions
- ✅ **Strict & Intelligence-Based Verification** — choose between deterministic Python validators or LLM-evaluated correctness
- 🔗 **Flow Testing** — define ordered sequences of HTTP interactions for multi-step scenario testing
- 🏷️ **Rich Tagging System** — organize tests by category, priority, and concern domain
- 🌐 **HTTP-First Scope** — purpose-built for testing HTTP server applications (request/response, headers, status codes, body validation)

---

## Architecture

AnchorTest is built on **[LangGraph](https://github.com/langchain-ai/langgraph)**, using a stateful graph of agents to handle each phase of test generation:

```
┌──────────────────────────────────────────────────────────────────────┐
│                           AnchorTest Graph                           │
│                                                                      │
│                    New Spec Document (Phase 2+)                      │
│                              │                                       │
│   Input Document             │                                       │
│   (Phase 1)                  │                                       │
│        │                     ▼                                       │
│        │            ┌─────────────────┐                              │
│        │            │  Diff & Sync    │◀─────────────────────┐       │
│        │            │  Agent          │                      │       │
│        │            └────────┬────────┘                      │       │
│        │                     │ delta                         │       │
│        ▼                     ▼                               │       │
│   ┌──────────┐     ┌──────────────┐     ┌───────────────┐    │       │
│   │  Parser  │────▶│  Reasoner    │────▶│   Generator   │    │       │
│   │  Agent   │     │  Agent       │     │   Agent       │    │       │
│   └──────────┘     └──────────────┘     └───────┬───────┘    │       │
│                                                 │            │       |
│                                                 ▼            │       |
│                                       ┌─────────────────┐    │       │
│                                       │  Test Suite     │─── ┘       │
│                                       │  Output         │  (cycle)   │
│                                       └─────────────────┘            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Test Case Types

### 🔒 Strict Test Case
A deterministic test case where correctness is verified by a **user-provided Python function**.

```python
# Example strict validator
def verify_response(response):
    assert response.status_code == 200
    assert response.json()["user"]["id"] is not None
    assert "Authorization" in response.headers
```

- Full programmatic control over assertions
- Ideal for well-defined, unambiguous behaviors
- Fails fast with clear error messages

---

### 🤖 Intelligence-Based Test Case
A test case where the **expected behavior is described in natural language** and the actual response is evaluated by an LLM judge.

**Example description:**
> *"When an invalid email is submitted during registration, the server should respond with a clear, human-readable error message that guides the user to fix their input. The message should not expose internal system details."*

- Ideal for subjective, nuanced, or UX-oriented checks
- LLM evaluates semantic correctness, tone, and intent
- Useful when exact response format may vary

---

## Test Flow Types

> **Note:** The input format for defining test cases is determined by the structure of the requirements/spec document provided to AnchorTest. No fixed schema is enforced at this stage.

### ⚡ Simple Test (`simpleTest`)
A single **request → response** interaction. Captures the endpoint, HTTP method, request details, and expected response.

---

### 🔗 Flow Test (`flowTest`)
An **ordered sequence** of HTTP interactions where each step may depend on data extracted from the previous step. Designed for end-to-end multi-step workflows.

**Example scenario — Bank Account Lifecycle:**
1. Create Account → extract `account_id`
2. Deposit Funds → using `account_id`
3. Withdraw Funds → using `account_id`
4. Check Balance → verified via a **strict** Python validator
5. Close Account → verified via **intelligence-based** evaluation

---

## Tags System

Every test case carries one or more **tags** for filtering, grouping, and reporting:

| Tag | Description |
|-----|-------------|
| `core-feature` | Tests for primary, happy-path functionality |
| `edge-case` | Boundary conditions, limits, and unusual inputs |
| `wrong-format` | Malformed requests, invalid types, missing fields |
| `unit-test` | Isolated test of a single endpoint or function |
| `system-reliability` | Timeouts, retries, fault tolerance, recovery |
| `security` | Auth, authorization, injection, data leakage |
| `performance` | Response time, throughput, load behavior |
| `regression` | Tests guarding against previously fixed bugs |

Multiple tags can be applied to a single test case.

---

## Phases

AnchorTest operates in **iterative phases** aligned with your development cycle:

### Phase 1 — Initial Generation
- **Input**: Requirements document / specification (v1)
- **Output**: Full test suite generated from scratch
- Each test is named, described, typed, and tagged

### Phase 2+ — Incremental Evolution
- **Input**: Updated requirements / specification (vN)
- **Process**: The system compares the new spec against the existing test suite and:
  - ➕ **Adds** test cases for new requirements
  - ✏️ **Modifies** test cases for changed behaviors
  - 🗑️ **Deletes** test cases for removed or deprecated features
- **Output**: Updated, synchronized test suite

---

## Getting Started

> ⚠️ **Prerequisites**: Python 3.10+, an OpenAI-compatible LLM API key

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/AnchorTest.git
cd AnchorTest
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Add your LLM API key and any other required config
```

### 4. Run Phase 1 — Generate Initial Test Suite

```bash
python -m anchortest generate --spec docs/requirements_v1.md --output tests/suite_v1.json
```

### 5. Run Phase 2+ — Update Test Suite

```bash
python -m anchortest update \
  --spec docs/requirements_v2.md \
  --existing tests/suite_v1.json \
  --output tests/suite_v2.json
```

---

## Project Structure

```
AnchorTest/
├── anchortest/
│   ├── graph/              # LangGraph nodes and edges
│   │   ├── parser.py       # Requirement document parser agent
│   │   ├── reasoner.py     # Test reasoning and planning agent
│   │   ├── generator.py    # Test case generation agent
│   │   └── diff.py         # Diff & sync agent (Phase 2+)
│   ├── models/
│   │   ├── test_case.py    # TestCase, SimpleTest, FlowTest schemas
│   │   └── suite.py        # TestSuite schema
│   ├── verifiers/
│   │   ├── strict.py       # Python function-based verifier
│   │   └── intelligence.py # LLM-based verifier
│   └── cli.py              # CLI entry point
├── tests/                  # Self-tests for AnchorTest
├── .env.example
├── requirements.txt
└── README.md
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  <sub>Built with ⚓ and LangGraph · Made for developers who ship with confidence</sub>
</div>
