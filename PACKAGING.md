# 打包须知（terminal-insight-v2）

## 环境前提

| 项 | 要求 |
|---|---|
| Python | 3.10+ |
| PyInstaller | `>=6.0` |
| GUI 依赖 | `pip install -e ".[gui]"` + `pip install "pyinstaller>=6.0"` |
| Windows | Edge WebView2（Win11 自带；Win10 装 [Runtime](https://developer.microsoft.com/microsoft-edge/webview2/)） |
| 原则 | **在目标系统上打包**（勿在 macOS 交叉编 Windows exe） |

## Windows 打包命令

```powershell
cd terminal-insight-v2
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[gui]"
pip install "pyinstaller>=6.0"

# Anaconda 若装了旧 pathlib backport：
# pip uninstall pathlib

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
python -W ignore -m PyInstaller build.spec --noconfirm
```

产物：

```text
dist\terminal-insight-v2\
  terminal-insight-v2.exe
  _internal\...          # 含代码、gui/static、category_templates、schema
```

分发时拷贝整个 `dist\terminal-insight-v2\` 文件夹。

## macOS 打包命令

```bash
cd terminal-insight-v2
source .venv/bin/activate
pip install -e ".[gui]" "pyinstaller>=6.0"
rm -rf build dist
python -W ignore -m PyInstaller build.spec --noconfirm
```

产物：`dist/Terminal Insight v2.app`。

## 运行时布局（冻结）

| 路径 | 说明 |
|---|---|
| `exe` 同级 `.env` | 配置面板保存；**不打包**密钥 |
| `exe` 同级 `data/` | runs / memory；**不打包** |
| `_internal/category_templates/` | 内置品类 Excel；也可在 exe 旁放同名目录覆盖 |
| `_internal/terminal_insight_v2/gui/static/` | GUI 页面 |

首次启动：在 GUI「配置」填写 API Key 并保存。

## 常见陷阱

1. **`pathlib` 旧 backport** — Anaconda 的 `pathlib==1.0.1` 与 PyInstaller 冲突 → `pip uninstall pathlib`。
2. **必须用 onedir** — `build.spec` 已 `exclude_binaries=True` + `COLLECT`/`BUNDLE`。
3. **datas 打整个包** — 不能只打 `gui/static`，否则 schema SQL / 静态资源缺失。
4. **调试黑屏** — 临时把 `build.spec` 里 `console=False` 改为 `True` 重打，看控制台报错。
5. **改代码后** — 改 `gui/`、`stages/`、`build.spec`、`config.py` 必须重打包；改 `.env` / `data/` 不用。

## 验证清单

```powershell
# 静态页在包内
Select-String -Path "dist\terminal-insight-v2\_internal\terminal_insight_v2\gui\static\index.html" -Pattern "Terminal Insight v2" -Quiet

# 品类模板在包内
Test-Path "dist\terminal-insight-v2\_internal\category_templates\phone.xlsx"

# 启动（应弹出窗口）
.\dist\terminal-insight-v2\terminal-insight-v2.exe
```

## 与开发模式差异

| | 开发 `python run_gui.py` | 打包 exe |
|---|---|---|
| 项目根 | 仓库根目录 | exe 所在目录 |
| 静态资源 | `src/.../gui/static` | `_MEIPASS/terminal_insight_v2/gui` |
| 品类模板 | `category_templates/` | 优先 exe 旁，否则 `_MEIPASS/category_templates` |
