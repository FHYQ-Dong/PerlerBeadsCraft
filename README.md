# PerlerBeadsCraft

把任意图片转换成**拼豆（Perler / Hama beads）图纸**。

输入一张图片，输出三样东西：

| 产物 | 文件 | 用途 |
|------|------|------|
| 彩色成品预览 | `<名字>_preview.png` | 模拟拼好后的样子（圆珠 + 拼板网格） |
| 打印图纸 | `<名字>_chart.png` | 每格带字母符号、坐标轴、每 10 格加粗、右侧色号图例 |
| 用料清单 | `<名字>_beads.csv` | 每种颜色的色号、名称、HEX、所需颗数及合计 |

色卡使用官方 **Hama Midi 53 标准色**（色号 + HEX）。颜色匹配在 **CIE Lab** 色彩空间做最近邻，比 RGB 欧氏距离更贴近人眼感受。透明像素（alpha 低于阈值）会被识别为「空位」，不放珠子。

## 环境

- Python ≥ 3.14，使用 [uv](https://docs.astral.sh/uv/) 管理。
- 依赖：`pillow`、`numpy`、`matplotlib`（已写入 `pyproject.toml`）。

首次准备环境：

```bash
uv sync
```

> ⚠️ 当前机器设置了环境变量 `UV_DEFAULT_INDEX=...tuna.tsinghua...`（清华源），且该源近期 TLS 握手不稳定。
> 本项目已在 `pyproject.toml` 里把默认索引固定为阿里云源；但环境变量优先级更高，会在 `uv run` 自动同步时被使用。
> 如遇下载失败，任选其一：
> - 同步时显式指定可用源：`uv sync --default-index https://mirrors.aliyun.com/pypi/simple/`
> - 环境已装好后用 `uv run --no-sync ...` 跳过联网检查（见下方示例）。

## 使用

```bash
# 基本用法：宽 48 颗珠子，保持宽高比
uv run --no-sync perler 图片.png

# 指定宽度、限制用色数、自定义输出目录
uv run --no-sync perler 图片.png -w 58 -m 16 -o 我的图纸

# 也可以不依赖 console 脚本，直接用模块运行
uv run --no-sync python -m perlerbeadscraft 图片.png -w 40
```

环境装好后，`--no-sync` 仅用于规避上面提到的镜像源问题；网络正常时可省略。

### 参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `image` | 源图片（png/jpg/...） | 必填 |
| `-w, --width` | 图纸宽度（珠子数） | 不指定尺寸时为 48 |
| `--height` | 图纸高度（珠子数）。只给宽或高之一即按比例缩放 | — |
| `-m, --max-colors` | 限制使用的颜色种类数（多余颜色就近合并） | 不限制 |
| `-p, --palette` | 色卡（目前内置 `hama`） | `hama` |
| `-o, --out-dir` | 输出目录 | `output` |
| `--bead-size` | 预览图中每颗珠子的像素大小 | 24 |
| `--shape` | 预览珠子形状：`circle` / `square` | `circle` |
| `--alpha-threshold` | 源像素 alpha 低于此值视为空位（0–255） | 128 |
| `--no-symbols` | 图纸不画每格字母符号 | 关 |
| `--no-grid` | 预览图不画网格线 | 关 |

## 工作原理

1. **缩放**：把图片用 LANCZOS 缩到「珠子网格」大小，按比例保持宽高。
2. **匹配**：每格 RGB 转 Lab，与色卡每个颜色算 Lab 距离取最近色（`color.py`）。
3. **减色**（可选）：保留出现最多的 N 种颜色，其余按 Lab 距离合并到最近的保留色（`pattern.py`）。
4. **渲染**：
   - 预览图用 Pillow 把每格画成带孔圆珠 + 拼板网格（`render.py`）。
   - 图纸用 matplotlib 画符号网格 + 坐标 + 图例。

## 代码结构

```
perlerbeadscraft/
  palettes.py   # Hama Midi 53 色色卡 + BeadColor / Palette 数据结构
  color.py      # sRGB→Lab 转换、最近邻颜色匹配（numpy 向量化）
  pattern.py    # 图片→珠子网格、减色、用量统计
  render.py     # 彩色预览 + 符号图纸 + 图例
  cli.py        # 命令行入口（argparse）
main.py         # 等价入口：uv run main.py ...
```
