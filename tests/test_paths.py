"""Repo root works from cwd, a section folder, and the viralLoom nest."""

from pathlib import Path

from src.paths import find_repo_root


def test_root_from_package():
    root = find_repo_root()
    assert (root / "src" / "llm.py").is_file()
    assert (root / "Section_5_Autonomous_Workflows").is_dir()


def test_root_from_section_hint():
    section = Path(__file__).resolve().parents[1] / "Section_3_LangChain_GPT4"
    root = find_repo_root(section)
    assert (root / "src" / "llm.py").is_file()


def test_root_from_viralloom_nest():
    nest = Path(__file__).resolve().parents[5]  # viralLoom when this file lives in course_repo/tests
    # D:/project/viralLoom/data/udemy/courses/ai_agents_bootcamp/course_repo/tests
    # parents[0]=tests [1]=course_repo [2]=ai_agents_bootcamp [3]=courses [4]=udemy [5]=data [6]=viralLoom
    viralloom = Path(__file__).resolve().parents[6]
    if viralloom.name.lower() != "viralloom" and (viralloom / "data").is_dir() is False:
        return
    root = find_repo_root(viralloom)
    assert (root / "src" / "llm.py").is_file()
