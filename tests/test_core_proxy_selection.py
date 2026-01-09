import hera_mcp.server.core as core


def test_call_proxy_uses_blender_client_when_not_in_blender(monkeypatch):
    calls = {"wait": 0, "call": 0}

    def fake_wait_worker(timeout_s=5.0):
        calls["wait"] += 1

    def fake_call_tool(name, args):
        calls["call"] += 1
        return {"ok": True, "result": {"tool": name, "args": args}}

    monkeypatch.setattr(core, "_in_blender", lambda: False)
    monkeypatch.setattr(core, "wait_worker", fake_wait_worker)
    monkeypatch.setattr(core, "call_tool", fake_call_tool)

    res = core._call_proxy("blender.version", {})
    assert calls["wait"] == 1
    assert calls["call"] == 1
    assert res["ok"] is True
