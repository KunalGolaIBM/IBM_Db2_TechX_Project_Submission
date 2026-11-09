# LinkedIn post draft (edit before posting; add your PR link and demo video)

I built QuantumMedX for IBM Db2Hack 2026.

It is a research-support platform where five CrewAI agents audit a healthcare dataset, run classical ML baselines and a Qiskit quantum classifier (on a simulator), and write a report. IBM Db2 stores every dataset, experiment, result and agent action, and a verifier checks that every number in the report matches what is stored in Db2.

What I wanted to get right:
- Agents explain results; they never produce them. Metrics come from deterministic code and Db2.
- Honest quantum comparison: simulator only, no claim of quantum advantage.
- Reproducible: schema, setup steps and tests are in the repo.

Built with Db2, CrewAI, Qiskit, FastAPI and React. Research prototype, not a diagnostic tool.

Repo: <your pull request or fork link>
@IBM Db2 TechX @GL Bajaj Group of Institutions, Mathura #Db2Hack2026 #IBMDb2 #CrewAI #Qiskit #QuantumMachineLearning
