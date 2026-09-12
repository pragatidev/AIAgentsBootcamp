"""Starter suite. scores has no reducer. Fixture model is not required here."""

from __future__ import annotations

from typing import Annotated, get_origin, get_type_hints

import pytest

from graph import ParentState, fan_out, load_resumes, template_paths
from talentflow.graphs.score_resumes import load_resumes as load_finished


def test_scores_key_has_no_reducer():
    ann = get_type_hints(ParentState, include_extras=True)["scores"]
    assert get_origin(ann) is not Annotated
    assert ann is list or get_origin(ann) is list


def test_load_is_todo():
    with pytest.raises(NotImplementedError):
        load_resumes()


def test_fan_out_sends_one_per_resume():
    loaded = load_finished()
    sends = fan_out(loaded)
    assert len(sends) == len(loaded["resumes"])
    assert len(sends) == 10


def test_email_templates_exist():
    paths = template_paths()
    assert len(paths) == 3
    joined = " ".join(paths).lower()
    assert "excellent" in joined
    assert "rejection" in joined
