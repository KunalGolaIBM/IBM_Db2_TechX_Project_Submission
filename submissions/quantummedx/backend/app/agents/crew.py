"""CrewAI orchestration: five agents, sequential tasks, tools = Toolbox methods (real backend calls)."""
import json
import os

from app.agents.tools import AGENTS, Toolbox


class LLMNotConfigured(RuntimeError):
    pass


def make_llm():
    from crewai import LLM
    provider, model, key = os.getenv("LLM_PROVIDER"), os.getenv("LLM_MODEL"), os.getenv("LLM_API_KEY")
    if not (provider and model and key):
        raise LLMNotConfigured("Set LLM_PROVIDER, LLM_MODEL and LLM_API_KEY in .env to use CrewAI mode.")
    return LLM(model=f"{provider}/{model}", api_key=key, temperature=0)


def build_crew(box: Toolbox, llm):
    from crewai import Agent, Crew, Process, Task
    from crewai.tools import tool

    @tool("check_data_quality")
    def check_data_quality() -> str:
        """Compute dataset quality statistics (row counts, missing values, duplicates, class balance)."""
        return json.dumps(box.data_quality())

    @tool("analyze_feature_patterns")
    def analyze_feature_patterns() -> str:
        """Return the numeric features most correlated with the target (aggregate statistics only)."""
        return json.dumps(box.feature_patterns())

    @tool("train_classical_model")
    def train_classical_model(algorithm: str) -> str:
        """Train and evaluate a classical model. algorithm is one of: logistic_regression, random_forest, svm."""
        return json.dumps(box.run_classical(algorithm))

    @tool("run_quantum_vqc")
    def run_quantum_vqc() -> str:
        """Train and evaluate the Qiskit variational quantum classifier on a local simulator."""
        return json.dumps(box.run_quantum())

    @tool("fetch_stored_results")
    def fetch_stored_results() -> str:
        """Read all completed experiment metrics from IBM Db2. The only valid source of metrics."""
        return json.dumps(box.stored_results(), default=str)

    rule = "Never state a metric you did not read from a tool result. Do not give medical advice or diagnoses."

    def agent(key, role, goal, tools):
        return Agent(role=AGENTS[key], goal=goal, backstory=f"{role} {rule}", tools=tools, llm=llm, allow_delegation=False, verbose=False)

    a1 = agent("data", "You audit healthcare research datasets.", "Report dataset quality issues accurately.", [check_data_quality])
    a2 = agent("clinical", "You describe statistical patterns in research data.", "Summarize feature-target associations without causal or clinical claims.", [analyze_feature_patterns])
    a3 = agent("classical", "You run classical ML baselines.", "Train logistic regression and random forest baselines.", [train_classical_model])
    a4 = agent("quantum", "You run quantum ML experiments on simulators.", "Run the VQC and report simulator limitations.", [run_quantum_vqc])
    a5 = agent("research", "You verify results and write the research summary.", "Write a short evidence-based comparison using only stored results.", [fetch_stored_results])

    tasks = [
        Task(description="Check the dataset quality using your tool and summarize the findings.", expected_output="Short data-quality summary.", agent=a1),
        Task(description="Find the features most associated with the target using your tool and summarize.", expected_output="Short pattern summary.", agent=a2),
        Task(description="Train logistic_regression and random_forest using your tool (one call each).", expected_output="Experiment ids of both runs.", agent=a3),
        Task(description="Run the quantum VQC experiment once using your tool.", expected_output="Experiment id and simulator caveat.", agent=a4),
        Task(description=("Fetch stored results with your tool and write 3-5 sentences comparing classical and quantum results. "
                          "Use only numbers returned by the tool. State that results do not prove quantum advantage."),
             expected_output="A short factual comparison paragraph.", agent=a5),
    ]
    return Crew(agents=[a1, a2, a3, a4, a5], tasks=tasks, process=Process.sequential, verbose=False)
