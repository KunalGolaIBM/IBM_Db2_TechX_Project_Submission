# Demo video script (about 3 minutes)

Record your screen with narration. Keep Db2 and the backend already running.

1. **0:00 Intro (15 s).** "QuantumMedX compares classical machine learning with a quantum classifier on healthcare data. AI agents run the workflow and IBM Db2 stores everything."
2. **0:15 Db2 (25 s).** Show the sidebar status "Db2 connected". Optionally show the tables in the Db2 Developer Extension for VS Code.
3. **0:40 Dataset (30 s).** Upload `breast_cancer_wdbc.csv` with target `target`. Point at rows, columns, missing values, duplicates and class balance.
4. **1:10 Experiments (50 s).** Run logistic regression, then the quantum experiment. Say it runs on a simulator. Show the results table and chart, and the circuit diagram. Say: "One small run does not show quantum advantage."
5. **2:00 Agents (45 s).** Start an agent run. Show the five agents appearing in the activity timeline. Open one tool output. Say: "Each tool call is a row in AGENT_ACTIVITIES."
6. **2:45 Report (25 s).** Open the report. Show the results table, the narrative label and the verification line. Say: "Every number is checked against Db2."
7. **3:10 Close (10 s).** "Code, schema and setup steps are in the repository."

Tips: use CrewAI mode only if it has already worked for you; otherwise use the tool pipeline mode and say so. Upload the video and put the link in `submission.json` (`video_url`) and the LinkedIn post.
