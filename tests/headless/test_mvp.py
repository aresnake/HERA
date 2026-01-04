import json

from hera_mcp.tools.core import health
from hera_mcp.tools.scene import create_object, move_object, snapshot


def expect_envelope(env: dict, operation: str):
    assert env.get("operation") == operation
    assert "scene_state" in env
    assert env.get("scene_state") is not None
    assert env.get("status") in ("ok", "partial", "error")
    if env.get("status") == "error":
        raise AssertionError(env.get("error"))


def test_flow():
    health_env = health.run()
    expect_envelope(health_env, "health")

    create_env = create_object.run(
        {"type": "cube", "name": "hera_cube", "location": [1, 2, 3]}
    )
    expect_envelope(create_env, "scene.create_object")
    obj_data = create_env["data"]["object"]
    assert obj_data["name"] == "hera_cube"

    move_env = move_object.run({"name": "hera_cube", "delta": [1, 0, 0]})
    expect_envelope(move_env, "scene.move_object")
    moved_location = move_env["data"]["object"]["location"]
    assert round(moved_location[0], 3) == 2.0

    snap_env = snapshot.run({"limit": 2})
    expect_envelope(snap_env, "scene.snapshot")
    assert len(snap_env["data"]["objects"]) <= 2
    if snap_env.get("resume_token"):
        assert "offset" in snap_env["resume_token"]

    print(
        json.dumps(
            {
                "status": "ok",
                "created": obj_data["name"],
                "moved_to": moved_location,
                "snapshot_objects": len(snap_env["data"]["objects"]),
            }
        )
    )


if __name__ == "__main__":
    test_flow()
