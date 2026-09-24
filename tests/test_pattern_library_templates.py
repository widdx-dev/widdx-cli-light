"""Tests for ProjectTemplate and TemplateRegistry in core/learning/pattern_library.py."""

from __future__ import annotations


from core.learning.pattern_library import ProjectTemplate, TemplateRegistry


class TestProjectTemplate:
    """ProjectTemplate dataclass."""

    def test_minimal_template(self):
        t = ProjectTemplate(name="test", description="a test template")
        assert t.name == "test"
        assert t.files == {}
        assert t.dependencies == []

    def test_template_with_files(self):
        t = ProjectTemplate(
            name="web-app",
            description="A web app",
            files={"src/main.py": "print('hello')", "README.md": "# App"},
            dependencies=["fastapi"],
        )
        assert len(t.files) == 2
        assert t.dependencies == ["fastapi"]

    def test_to_dict_roundtrip(self):
        t = ProjectTemplate(
            name="test",
            description="desc",
            tags=["python"],
            files={"f1.py": "content"},
            dependencies=["dep1"],
            dev_dependencies=["dep2"],
            post_init_commands=["cmd1"],
        )
        d = t.to_dict()
        assert d["name"] == "test"
        assert d["tags"] == ["python"]

        restored = ProjectTemplate.from_dict(d)
        assert restored.name == "test"
        assert restored.tags == ["python"]
        assert restored.files == {"f1.py": "content"}


class TestTemplateRegistry:
    """TemplateRegistry with built-in templates."""

    def test_registry_has_builtins(self):
        tr = TemplateRegistry()
        templates = tr.list_all
        names = [t.name for t in templates]
        assert "fastapi-sqlalchemy" in names
        assert "nextjs-prisma" in names
        assert "python-cli" in names

    def test_get_returns_template(self):
        tr = TemplateRegistry()
        t = tr.get("fastapi-sqlalchemy")
        assert t is not None
        assert t.name == "fastapi-sqlalchemy"
        assert any("fastapi" in dep for dep in t.dependencies)

    def test_get_unknown_returns_none(self):
        tr = TemplateRegistry()
        assert tr.get("nonexistent-template") is None

    def test_search_by_name(self):
        tr = TemplateRegistry()
        results = tr.search(query="fastapi")
        assert len(results) >= 1
        assert results[0].name == "fastapi-sqlalchemy"

    def test_search_by_tags(self):
        tr = TemplateRegistry()
        results = tr.search(tags=["cli"])
        assert len(results) >= 1
        assert results[0].name == "python-cli"

    def test_search_empty_query_returns_all(self):
        tr = TemplateRegistry()
        results = tr.search(query="")
        assert len(results) == 3

    def test_register_custom_template(self):
        tr = TemplateRegistry()
        custom = ProjectTemplate(
            name="my-template",
            description="custom",
            files={"file.txt": "hello"},
        )
        tr.register(custom)
        assert tr.get("my-template") is custom

    def test_fastapi_template_has_post_init_commands(self):
        tr = TemplateRegistry()
        t = tr.get("fastapi-sqlalchemy")
        assert len(t.post_init_commands) >= 2

    def test_nextjs_template_has_files(self):
        tr = TemplateRegistry()
        t = tr.get("nextjs-prisma")
        assert "prisma/schema.prisma" in t.files
        assert "src/app/page.tsx" in t.files

    def test_python_cli_template_has_dev_deps(self):
        tr = TemplateRegistry()
        t = tr.get("python-cli")
        assert any("pytest" in dep for dep in t.dev_dependencies)
