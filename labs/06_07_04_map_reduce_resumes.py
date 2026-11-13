# %%
"""Lab 16.4: map-reduce over a batch of TalentFlow resumes.

What we build: the TalentFlow scorer on the whole pile, ten resumes against one job description. load reads
the job and the resumes. A routing function, fan_out, returns one Send per resume, so one node, score, drawn
once on the map, runs as ten copies, each with its own small packet: the candidate's name, the resume text and
the job. Each copy asks the model for a score, a fit and a reason, and returns a one-item list. summarize sorts
the gathered list into a table and asks the model for three sentences. You type the parent notebook,
ParentState, with the reducer on scores, fan_out, and score. summarize and the builder are the package's, and
we walk them line by line.

What you learn: Send is how you fan out over a list whose length you only know at run time. Each Send becomes
its own task with its own input, so a copy never sees the whole notebook, only its packet. The copies share one
superstep, and their writes are applied together when it ends, so scores must add lists, exactly as the two
lookups did in Lab 16.2. On a local Ollama the copies are served one at a time, so the batch takes as long as
ten calls in a row; on a hosted provider they run side by side.

What will be true on your screen: the model line and the versions, resumes_loaded 10 and sends 10, one copy's
packet (its keys, the candidate, the sizes of the resume and the job), the elapsed seconds, the ten names in
the order their scores were gathered, the ranking table with the model's three sentences, the note on Ollama,
then the history oldest first with one step whose next holds score ten times. With the break, every copy
calls the model, and only then does the run stop on InvalidUpdateError: At key 'scores': Can receive only one
value per step.
"""

from collections import Counter
from importlib.metadata import version
from pathlib import Path
import operator
import sys
import time
from typing import Annotated, TypedDict

root = Path(__file__).resolve().parents[1] if "__file__" in globals() else Path.cwd()
sys.path.insert(0, str(root))

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Send

import config
from dataflow.envelope import DeskContext
from talentflow.graphs.score_resumes import SCORE_SYSTEM, ResumeScore, ScoreInput, load_resumes, summarize

chat = config.get_chat_model()
print("model", type(chat).__name__, getattr(chat, "model", None) or getattr(chat, "model_name", None))
print("langchain-core", version("langchain-core"))
print("langgraph", version("langgraph"))


# %%
# TYPE THIS: ParentState, fan_out and score. The signatures and docstrings are given; you type the rest.
# The package's finished version is ParentState, fan_out and score in talentflow/graphs/score_resumes.py
# (lines 53 to 57, 99 to 105 and 136 to 173).
class ParentState(TypedDict, total=False):
    """The job, the pile, the scores every copy adds to, and the ranking."""
    job: str
    resumes: list[dict]
    scores: Annotated[list, operator.add]
    ranking: str


def fan_out(state: ParentState) -> list[Send]:
    """One Send per resume. Each packet carries only what that copy needs."""
    job = state["job"]
    return [Send("score", {"name": r["name"], "text": r["text"], "job": job}) for r in state["resumes"]]


def score(state: ScoreInput) -> dict:
    """Score one resume against the job. Returns a one-item list for the reducer."""
    reader = chat.with_structured_output(ResumeScore)
    prompt = "Candidate: " + state["name"] + "\n\nJob description:\n" + state["job"] + "\n\nResume:\n" + state["text"]
    decision = reader.invoke(
        [
            {"role": "system", "content": SCORE_SYSTEM},
            {"role": "user", "content": prompt},
        ]
    )
    row = {"name": state["name"], "score": int(decision.score), "fit": str(decision.fit), "reason": str(decision.reason)}
    return {"scores": [row]}


# BREAK: change the scores line of ParentState to scores: list (take operator.add off) and run. It compiles, load
# runs, all ten copies call the model (watch the time), and only then does the run stop on InvalidUpdateError: At
# key 'scores': Can receive only one value per step. The writes are applied when the step ends, so you pay for
# every copy and keep none of them. Put it back and run.

# %%
# Given, and walked line by line: load, rank and the builder. load reads the pile; fan_out is the edge out of load,
# and score is the only node it may send to; every copy leads to summarize, which runs once, after the step that
# ran them all. rank is typed on your ParentState because LangGraph reads a node's type hint as its input: the
# package's summarize is typed on the package's ParentState and would bring that notebook's scores key with it.
def load(state: ParentState) -> dict:
    """Read the job description and every resume file."""
    return load_resumes()


def rank(state: ParentState, runtime: Runtime[DeskContext]) -> dict:
    """The package's summarize: sort the scores into a table, ask the model for three sentences."""
    return summarize(state, runtime=runtime)


def build_map_reduce():
    builder = StateGraph(ParentState, context_schema=DeskContext)
    builder.add_node("load", load)
    builder.add_node("score", score)
    builder.add_node("summarize", rank)
    builder.add_edge(START, "load")
    builder.add_conditional_edges("load", fan_out, ["score"])
    builder.add_edge("score", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile(checkpointer=InMemorySaver())


# %%
# One copy's packet, before anything runs.
loaded = load_resumes()
sends = fan_out(loaded)
print("resumes_loaded", len(loaded["resumes"]), "sends", len(sends))
first = sends[0]
print("one_packet node", first.node, "keys", sorted(first.arg), "name", first.arg["name"])
print("one_packet resume_chars", len(first.arg["text"]), "job_chars", len(first.arg["job"]))

# %%
graph = build_map_reduce()
thread = {"configurable": {"thread_id": "lab-16-4"}}
started = time.perf_counter()
out = graph.invoke({}, thread, context=DeskContext(model=chat))
print("elapsed_seconds", round(time.perf_counter() - started, 1))
gathered = [row["name"] for row in out["scores"]]
print("gathered_order", gathered)
print("same_order_as_sends", gathered == [s.arg["name"] for s in sends])
print("ranking")
print(out["ranking"])
print("ollama_note a local Ollama serves the ten copies one at a time; on a hosted provider they run side by side")

# %%
history = list(reversed(list(graph.get_state_history(thread))))
print("history_oldest_first", len(history))
for snap in history:
    print("step", snap.metadata["step"], "next", dict(Counter(snap.next)))
