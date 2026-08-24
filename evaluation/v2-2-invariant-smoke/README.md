# SolutionScope v2.2 invariant smoke

This deterministic engineering smoke demonstrates two behaviors that a retrieval-only RAG does not guarantee:

- a cited but weaker solution commitment (`>= 90%`) is blocked against the requirement (`>= 92%`), even if the model labels the component covered;
- equivalent units (`<= 600 ms` and `<= 0.6 s`) are normalized and accepted rather than treated as a mismatch.

The fixtures are synthetic and manually authored to exercise the gate. They are not an accuracy benchmark or evidence of generalization.
