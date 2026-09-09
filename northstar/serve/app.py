"""HTTP door. S23 fills FastAPI. Tests call health() with no extra packages."""


def health() -> dict:
    return {"ok": True, "service": "northstar"}
