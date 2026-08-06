# 希沃一体机优化工具（Seewon Optimizer）

单文件 Windows 工具，双击即用，零依赖零安装。专为希沃一体机日常维护设计。

## 功能

| 模块 | 说明 |
|------|------|
| 🚀 一键优化系统 | 清理临时文件/启动项/服务/注册表，释放内存，整理磁盘，清理希沃缓存，关闭 Windows 贴靠布局 |
| ↩️ 一键还原系统 | 精确回滚本次优化改过的项；或调起 Windows 系统还原点整体回退 |
| 📦 常用软件安装 | 优先使用本地离线包，缺失则在线下载，静默安装 |
| 🎓 教学工具安装 | 安装包静默安装；或压缩包解压到 D 盘并创建开始菜单快捷方式 |
| 🖼️ 希沃壁纸更换 | 从壁纸文件夹列表选择并设为桌面/锁屏壁纸 |

## 下载

最新构建产物（exe）通过 [Nightly.link](https://nightly.link) 下载：

👉 [下载最新构建](https://nightly.link/fengjian868/seewon-optimizer/workflows/build/main/希沃一体机优化工具.zip)

或前往 [Actions 页面](https://github.com/fengjian868/seewon-optimizer/actions) 手动选择某次运行下载 artifact。

## 使用

1. 下载 exe 后放到任意目录
2. 同级会自动创建三个文件夹（首次运行）：
   - `常用软件/` — 放常用软件离线安装包
   - `教学工具/` — 放教学工具安装包或压缩包
   - `壁纸/` — 放壁纸图片
3. 双击 `希沃一体机优化工具.exe`，授权 UAC 后即可使用

## 软件元数据

软件/教学工具的安装规则在 `assets/software.json` 和 `assets/teaching_tools.json`。可根据实际安装包增删条目，字段说明：

- `id`：唯一标识
- `name`：显示名称
- `deploy`：`install`（静默安装）或 `extract`（解压部署）
- `detect_reg` / `detect_path`：判断是否已安装的规则
- `offline_file`：本地离线包文件名（需放入对应文件夹）
- `download_url`：无本地包时在线下载地址
- `silent_args`：静默安装参数（install 方式）
- `target_dir` + `main_exe`：解压目标目录与主程序（extract 方式）

## 从源码构建

```bash
pip install -r requirements.txt
pyinstaller build.spec
# 产物：dist/希沃一体机优化工具.exe
```

## 技术栈

- Python 3.10+ / tkinter（轻量 GUI）
- PyInstaller `--onefile --windowed` 单文件打包
- UAC manifest 嵌入 `requireAdministrator`（启动即提权）

## 许可证

MIT
