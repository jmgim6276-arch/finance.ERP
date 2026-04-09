# finance.ERP

财税通 ERP 档案关系配置脚本。

## Files

- `scripts/cst_live_mapper.py`
  复用当前已登录的 Edge/Chrome 财税通页面，自动处理:
  - 科目费用类型对应关系
  - 往来单位对应关系
  - 人员对应关系
  - 项目对应关系
  - 部门对应关系
- `scripts/browser_session.py`
  浏览器会话接管工具，负责连接本机浏览器的 DevTools，会被主脚本调用。

## Requirements

- macOS
- Python 3
- Microsoft Edge 或 Google Chrome
- 浏览器里已经登录财税通
- 本机安装依赖:

```bash
python3 -m pip install -r requirements.txt
```

## Usage

先在 Edge 中手动登录财税通，并进入任意财税通页面，然后执行:

```bash
python3 scripts/cst_live_mapper.py --apply
```

脚本会优先接管当前已登录的浏览器会话，不会自动放宽匹配规则。

只做检查、不保存时:

```bash
python3 scripts/cst_live_mapper.py
```

执行后会生成 `cst_live_mapper_report.json`，用于查看哪些项被跳过。

## Matching Rules

- 项目、部门:
  只允许精确命中两列中的某一列。
- 如果两列各自命中不同候选:
  视为歧义，留空。
- 科目:
  按当前脚本里的最长后缀链精确匹配。
- 没有可靠匹配时:
  留空，不猜。

## OpenClaw Prompt

在另一台电脑上，可以直接对 OpenClaw 说:

```text
进入这个仓库目录，复用当前已登录的 Edge 财税通会话，执行 `python3 scripts/cst_live_mapper.py --apply`。
如果没有检测到已登录的财税通页面，就停下并提醒我先手动登录。
执行完成后读取 `cst_live_mapper_report.json`，告诉我哪些项目被跳过。
不要放宽匹配规则。
```
