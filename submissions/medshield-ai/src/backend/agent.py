"""Small LangGraph workflow for transparent rule-based medication screening."""
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

class SafetyState(TypedDict, total=False):
    medications: List[str]
    allergies: List[str]
    findings: List[Dict[str, str]]
    risk: str
    summary: str

def normalize(state):
    meds=[m.strip().lower() for m in state.get('medications',[]) if m.strip()]
    return {"medications": meds}

def screen(state):
    meds=state.get('medications',[]); allergies=[a.lower() for a in state.get('allergies',[])]
    findings=[]
    for med in meds:
        if med in allergies:
            findings.append({"type":"ALLERGY","severity":"HIGH","message":f"{med.title()} matches a listed allergy."})
    if len(meds) != len(set(meds)):
        findings.append({"type":"DUPLICATE","severity":"MODERATE","message":"A medication appears more than once."})
    pairs={frozenset(("warfarin","ibuprofen")): ("HIGH","May increase bleeding risk."),
           frozenset(("lisinopril","potassium")): ("MODERATE","May increase potassium levels.")}
    for i,a in enumerate(meds):
        for b in meds[i+1:]:
            if frozenset((a,b)) in pairs:
                sev,msg=pairs[frozenset((a,b))]
                findings.append({"type":"INTERACTION","severity":sev,"message":f"{a.title()} + {b.title()}: {msg}"})
    return {"findings":findings}

def assess(state):
    levels=[f['severity'] for f in state.get('findings',[])]
    risk="HIGH" if "HIGH" in levels else "MODERATE" if "MODERATE" in levels else "LOW"
    summary="No demo-rule alerts found. This is not proof that the regimen is safe." if not levels else f"{len(levels)} potential safety finding(s) require review."
    return {"risk":risk,"summary":summary}

def build_graph():
    g=StateGraph(SafetyState)
    g.add_node("normalize",normalize); g.add_node("screen",screen); g.add_node("assess",assess)
    g.set_entry_point("normalize"); g.add_edge("normalize","screen"); g.add_edge("screen","assess"); g.add_edge("assess",END)
    return g.compile()

workflow=build_graph()

def analyze(medications, allergies):
    return workflow.invoke({"medications":medications,"allergies":allergies})
