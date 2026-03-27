# Code Flow Skill Package

Standalone packaging of the Code Flow skill as:
- npm package: `@red-sea/code-flow-skill`
- Python package for `uvx`: `red-sea-code-flow-skill`

## Install

### npm

```bash
npm i -g @red-sea/code-flow-skill
code-flow-skill --tool all --target .
```

### uvx

```bash
uvx red-sea-code-flow-skill --tool all --target .
```

## CLI Options

```text
--tool claude|gemini|copilot|all
--target <path>
```

Defaults:
- `--tool all`
- `--target .`

## What gets installed

- Claude: `.claude/commands/code-flow.md`
- Gemini: `.gemini/commands/code-flow.toml`
- Copilot: appends Code Flow section to `.github/copilot-instructions.md`

## Publish

### npm

```bash
npm publish --access public
```

### PyPI

```bash
uv build
uv publish
```
