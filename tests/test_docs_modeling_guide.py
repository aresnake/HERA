from pathlib import Path


def test_modeling_guide_exists_and_mentions_tools():
    doc = Path("docs/CLAUDE_MODELING_GUIDE.md")
    assert doc.exists(), f"missing {doc}"
    text = doc.read_text(encoding="utf-8")
    for name in [
        "hera.blender.batch",
        "hera.blender.mesh.create_cube",
        "hera.blender.mesh.create_uv_sphere",
        "hera.blender.mesh.create_cylinder",
        "hera.blender.object.rename",
        "hera.blender.object.delete",
        "hera.blender.object.set_transform",
        "hera.blender.object.get_transform",
        "hera.blender.object.exists",
        "hera.blender.object.get_location",
    ]:
        assert name in text, f"missing tool name in doc: {name}"
