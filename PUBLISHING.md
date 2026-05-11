# Publishing `homedata-mcp` to PyPI

This package is intended for distribution on [PyPI](https://pypi.org). The
release process is currently manual.

## Prerequisites

1. A PyPI account at <https://pypi.org/account/register/> with the
   `homedata-mcp` project (claim the name on first publish).
2. A PyPI API token scoped to the project (or to the whole account for the
   first publish): <https://pypi.org/manage/account/token/>.
3. Optional - a TestPyPI account at <https://test.pypi.org> for dry runs.

Store credentials as environment variables (preferred over `~/.pypirc`):

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Build

```bash
cd homedata-mcp
rm -rf dist build *.egg-info
python -m pip install --upgrade build twine
python -m build
```

This produces:

```
dist/homedata_mcp-<version>.tar.gz          # sdist
dist/homedata_mcp-<version>-py3-none-any.whl # wheel
```

## Validate

```bash
python -m twine check dist/*
```

Both the sdist and wheel must report `PASSED`.

## Dry run on TestPyPI (recommended)

```bash
python -m twine upload --repository testpypi dist/*
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            homedata-mcp
homedata-mcp --version
```

## Publish to PyPI

```bash
python -m twine upload dist/*
```

The first upload claims the `homedata-mcp` project name on PyPI. After that,
only token holders for the project can publish further releases.

## Cutting a new version

1. Bump `version` in `pyproject.toml` and `homedata_mcp/__init__.py`
   (they must match).
2. Bump `User-Agent` in `homedata_mcp/client.py` to match.
3. Add a section to `CHANGELOG.md`.
4. Tag the release: `git tag vX.Y.Z && git push --tags`.
5. Build, validate, and publish (steps above).

## Automated publishing via GitHub Actions (OIDC trusted publisher)

A GitHub Actions workflow at [`.github/workflows/release.yml`](.github/workflows/release.yml) publishes the package to PyPI automatically when a release tag is pushed.
It uses [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/)
over OIDC, so **no PyPI API tokens or repository secrets are required**.

### How to cut a release

1. Bump `version` in `pyproject.toml` and `homedata_mcp/__init__.py`
   (they must match), update `User-Agent` in `homedata_mcp/client.py`, and
   add a `CHANGELOG.md` section. Commit and merge to `main`.
2. From `main`, tag the release and push the tag:

   ```bash
   git checkout main && git pull
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. The workflow runs automatically:
   - **build** job: checks out the repo, sets up Python 3.13, installs
     `build` + `twine`, runs `python -m build` and `python -m twine check`, and uploads `dist/` as an artifact.
   - **publish** job: downloads the artifact and publishes to PyPI via
     `pypa/gh-action-pypi-publish` using OIDC.
4. Confirm the new version appears at
   <https://pypi.org/project/homedata-mcp/>.

The workflow triggers **only** on tags matching `v*` — never on
regular commits or pull requests.

### Trusted publisher configuration (one-time, already done)

On PyPI, the `homedata-mcp` project has a GitHub trusted publisher
registered with:

| Field                | Value                          |
|----------------------|--------------------------------|
| Owner                | `wehomemove`           |
| Repository name      | `homedata-mcp`         |
| Workflow filename    | `release.yml`          |
| Environment          | _(blank)_              |

If you ever need to rotate the trusted publisher, update both PyPI's
project settings and this section together.
