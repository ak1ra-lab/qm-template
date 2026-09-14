# qm-template

Proxmox VE template helper scripts

## 亮点

- 基于 `uv`, `ruff`, `ty`, `pytest`, `mkdocs-material` 构建。
- CLI 使用 `argparse` 和 `argcomplete` 提供 Shell 补全。
- 从 `src/qm_template` 打包发布。
- 已发布的文档位于 <https://ak1ra-lab.github.io/qm-template/>。

## 快速开始

```bash
uv sync --group dev
uv run qm-template --version
```
