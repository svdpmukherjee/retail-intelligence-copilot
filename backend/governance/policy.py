from typing import Literal

from retrieval.vector_store import Filters

Role = Literal["executive", "admin", "analyst", "support", "marketing"]

# {} is unrestricted. Scoped roles only use keys build_where accepts; `source_type` is left out
# on purpose because each RAG agent pins it itself and that pin must keep winning.
ACCESS_POLICY: dict[str, Filters] = {
    "executive": {},
    "admin": {},
    "analyst": {},
    "support": {"category": ["Electronics", "Home_and_Kitchen", "Automotive", "Pet_Supplies"]},
    "marketing": {"category": ["Beauty_and_Personal_Care", "Toys_and_Games", "Books"]},
}


class AccessDenied(Exception):
    """The role has no entry in the access policy; message is safe to show."""


def scope_for_role(role: str) -> Filters:
    """Retrieval/SQL scope for `role`; deny-by-default for unknown or empty roles."""
    if not role or role not in ACCESS_POLICY:
        raise AccessDenied(f"role {role!r} has no access policy")
    return {key: list(v) if isinstance(v, list) else v for key, v in ACCESS_POLICY[role].items()}
