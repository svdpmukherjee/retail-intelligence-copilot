import asyncio

import pytest
from fastapi.testclient import TestClient

from agents import pipeline
from agents.router import derive_scope
from app.main import app
from governance.policy import ACCESS_POLICY, AccessDenied, scope_for_role
from retrieval.vector_store import FILTER_COLUMNS, build_where


def test_full_access_role_is_unrestricted_and_scoped_roles_are_not() -> None:
    assert scope_for_role("executive") == scope_for_role("admin") == {}
    assert scope_for_role("support") and scope_for_role("marketing")


def test_two_roles_yield_different_where_params() -> None:
    exec_where, exec_params = build_where(scope_for_role("executive"))
    sup_where, sup_params = build_where(scope_for_role("support"))
    mkt_where, mkt_params = build_where(scope_for_role("marketing"))
    assert (exec_where, exec_params) == ("", [])
    assert "category = ANY(%s)" in sup_where
    assert sup_params != mkt_params and set(sup_params[0]).isdisjoint(mkt_params[0])


def test_policy_only_uses_accepted_filter_keys() -> None:
    for scope in ACCESS_POLICY.values():
        assert set(scope) <= set(FILTER_COLUMNS)
        build_where(scope)


@pytest.mark.parametrize("role", ["", "intruder", "Executive"])
def test_unknown_or_empty_role_is_denied(role) -> None:
    with pytest.raises(AccessDenied):
        scope_for_role(role)
    with pytest.raises(AccessDenied):
        derive_scope(role)


def test_returned_scope_is_a_copy() -> None:
    scope_for_role("support")["category"].append("X")
    assert "X" not in ACCESS_POLICY["support"]["category"]


def test_source_type_pin_still_wins_over_scope() -> None:
    where, params = build_where({**scope_for_role("support"), "source_type": "review"})
    assert "source_type = %s" in where and "review" in params


def test_pipeline_maps_access_denied_to_pipeline_error() -> None:
    with pytest.raises(pipeline.PipelineError, match="AccessDenied"):
        asyncio.run(pipeline.answer("anything", "intruder"))


def test_query_endpoint_returns_502_for_denied_role() -> None:
    resp = TestClient(app).post("/query", json={"query": "hi", "role": "intruder"})
    assert resp.status_code == 502
    assert "AccessDenied" in resp.json()["detail"]
