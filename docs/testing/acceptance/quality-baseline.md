# Answer-quality baseline

Mode: **fixture**.

12 authored review rows; 6 products; 4 categories; January 2023. Not a representative retail sample.

No aggregate faithfulness score is claimed.

- No browser or semantic-support reviewer executed.
- Ephemeral memory: DB ownership/persistence and cross-thread findings untested.
- Finish reason and source/index versions not exposed by runtime adapters.
- Synthetic contracts, not real LLM/embedding quality.

Cases: {'PASS': 0, 'FAIL': 12, 'NOT RUN': 22}
Assertions: {'PASS': 79, 'FAIL': 29, 'NOT RUN': 70}

| Case | Role | Status | Failed or unmeasured checks |
|---|---|---|---|
| A01 | marketing | FAIL | requested category: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A01 | executive | FAIL | requested category: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A02 | marketing | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A02 | executive | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A03 | marketing | FAIL | required tools: FAIL; standalone query: FAIL; requested category: FAIL; selected product gold: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A03 | executive | FAIL | required tools: FAIL; standalone query: FAIL; requested category: FAIL; selected product gold: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A04 | marketing | FAIL | required tools: FAIL; SQL product scope: NOT RUN; requested category: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A04 | executive | FAIL | required tools: FAIL; standalone query: FAIL; SQL product scope: NOT RUN; requested category: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A05 | marketing | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A05 | executive | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A06 | marketing | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A06 | executive | NOT RUN | qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A07 | marketing | FAIL | required tools: FAIL; SQL product scope: NOT RUN; requested category: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A07 | executive | FAIL | required tools: FAIL; SQL product scope: NOT RUN; requested category: FAIL; product evidence join: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A08 | marketing | NOT RUN | qualitative support: NOT RUN; browser semantics: NOT RUN; live generation and retrieval: NOT RUN |
| A08 | executive | NOT RUN | qualitative support: NOT RUN; browser semantics: NOT RUN; live generation and retrieval: NOT RUN |
| A09 | marketing | NOT RUN | qualitative support: NOT RUN; browser semantics: NOT RUN; live generation and retrieval: NOT RUN |
| A09 | executive | NOT RUN | qualitative support: NOT RUN; browser semantics: NOT RUN; live generation and retrieval: NOT RUN |
| A10 | marketing | FAIL | SQL product scope: NOT RUN; empty is not evidence: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A10 | executive | FAIL | SQL product scope: NOT RUN; empty is not evidence: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A11 | marketing | FAIL | requested category: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A11 | executive | FAIL | requested category: FAIL; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A12 | marketing | NOT RUN | SQL product scope: NOT RUN; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A12 | executive | NOT RUN | SQL product scope: NOT RUN; qualitative support: NOT RUN; live generation and retrieval: NOT RUN |
| A13 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A14 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A15 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A16 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A17 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A18 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A19 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A20 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A21 | both | NOT RUN | boundary instrumentation: NOT RUN |
| A22 | both | NOT RUN | boundary instrumentation: NOT RUN |

See companion JSON for expectations, assertion reasons and evidence.
Synthetic results must not be presented as live answer-quality validation.
