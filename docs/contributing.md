--8<-- "CONTRIBUTING.md"

## Working on the docs

This site is [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).
The sources are the Markdown files under `docs/`, and the navigation is the `nav:`
list in `mkdocs.yml`.

```bash
uv sync --group docs
uv run poe docs          # serve at http://127.0.0.1:8000 with live reload
uv run poe docs-build    # build into site/, failing on broken links
```

`docs-build` runs `mkdocs build --strict`, which turns warnings — a broken internal
link, a page missing from the nav — into errors. That is what CI runs on every pull
request, so run it before pushing documentation changes.

`contributing.md` and `changelog.md` are one-line snippet includes of
`CONTRIBUTING.md` and `CHANGELOG.md` at the repository root. Edit those files, not
the pages under `docs/`, so GitHub and the site never disagree.

Pushing to `main` deploys the site to GitHub Pages automatically.
