"""Project scaffolder — create new projects from templates."""

import logging
from pathlib import Path

logger = logging.getLogger("widdx.tools.scaffolder")

_TEMPLATES = {
    "python-cli": {
        "pyproject.toml": """[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.10"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"
""",
        "{name}/__init__.py": "",
        "{name}/__main__.py": """def main():
    print("Hello from {name}!")


if __name__ == "__main__":
    main()
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "__pycache__/\n*.pyc\n*.egg-info/\ndist/\nbuild/\n",
    },
    "python-web": {
        "pyproject.toml": """[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"
""",
        "{name}/__init__.py": "",
        "{name}/main.py": """from fastapi import FastAPI

app = FastAPI(title="{name}")


@app.get("/")
async def root():
    return {{"message": "Hello from {name}"}}
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "__pycache__/\n*.pyc\n*.egg-info/\ndist/\nbuild/\n",
    },
    "node-cli": {
        "package.json": """{{
  "name": "{name}",
  "version": "1.0.0",
  "description": "{description}",
  "main": "index.js",
  "scripts": {{
    "start": "node index.js"
  }},
  "dependencies": {{}}
}}
""",
        "index.js": """#!/usr/bin/env node

function main() {
    console.log("Hello from {name}!");
}

main();
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "node_modules/\n",
    },
    "node-express": {
        "package.json": """{{
  "name": "{name}",
  "version": "1.0.0",
  "description": "{description}",
  "main": "index.js",
  "scripts": {{
    "start": "node index.js"
  }},
  "dependencies": {{
    "express": "^4.18.0"
  }}
}}
""",
        "index.js": """const express = require("express");
const app = express();
const port = process.env.PORT || 3000;

app.get("/", (req, res) => {
    res.json({ message: "Hello from {name}!" });
});

app.listen(port, () => {
    console.log(`{name} listening on port ${port}`);
});
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "node_modules/\n",
    },
    "rust-cli": {
        "Cargo.toml": """[package]
name = "{name}"
version = "0.1.0"
edition = "2021"
description = "{description}"

[dependencies]
""",
        "src/main.rs": """fn main() {
    println!("Hello from {name}!");
}
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "/target\n",
    },
    "go-cli": {
        "go.mod": "module {name}\n\ngo 1.22\n",
        "main.go": """package main

import "fmt"

func main() {{
    fmt.Println("Hello from {name}!")
}}
""",
        "README.md": "# {name}\n\n{description}\n",
        ".gitignore": "/*.exe\n",
    },
}


import string


class _SafeFormatter(string.Formatter):
    def format_field(self, value, format_spec):
        if value is None:
            return "{" + format_spec + "}" if format_spec else ""
        return super().format_field(value, format_spec)

    def get_value(self, key, args, kwargs):
        try:
            return super().get_value(key, args, kwargs)
        except KeyError:
            return "{" + str(key) + "}"


def _scaffold(template: str = "python-cli", name: str = "my-project",
              path: str | None = None, description: str = "") -> str:
    """Scaffold a new project from a template."""
    if template not in _TEMPLATES:
        available = ", ".join(_TEMPLATES.keys())
        return f"Unknown template: {template}. Available: {available}"

    root = Path(path) if path else Path.cwd() / name
    root = root.resolve()

    if root.exists():
        return f"Directory already exists: {root}"

    if not description:
        description = f"A {template} project"

    safe_fmt = _SafeFormatter()
    files = _TEMPLATES[template]
    created = []
    for rel_path, content in files.items():
        safe_rel = rel_path.format(name=name.replace("-", "_").replace(" ", "_"))
        filepath = root / safe_rel
        filepath.parent.mkdir(parents=True, exist_ok=True)
        fmt_content = safe_fmt.format(content, name=name, description=description)
        filepath.write_text(fmt_content, encoding="utf-8")
        created.append(str(filepath.relative_to(root)))

    # Create .widdx docs
    from core.project_tracker import ensure_docs
    ensure_docs(root)

    buf = [
        f"✅ Scaffolded '{template}' project: {root.name}/",
        "",
    ]
    for f in created:
        buf.append(f"  📄 {f}")
    buf.append("")
    buf.append(f"  cd {root.name}  to get started")
    return "\n".join(buf)
