# 希沃一体机优化工具（Seewon Optimizer）

单文件 Windows 工具，双击即用，零依赖零安装。专为希沃一体机日常维护设计。

## 功能

| 模块 | 说明 |
|------|------|
| 🚀 一键优化系统 | 清理临时文件/启动项/服务/注册表，释放内存，整理磁盘，清理希沃缓存，关闭 Windows 贴靠布局 |
| ↩️ 一键还原系统 | 精确回滚本次优化改过的项；或调起 Windows 系统还原点整体回退 |
| 🖼️ 希沃壁纸更换 | 从壁纸文件夹列表选择并设为桌面/锁屏壁纸 |

## 下载

最新构建产物（exe）通过 [Nightly.link](https://nightly.link) 下载：

👉 [下载最新构建](https://nightly.link/fengjian868/seewon-optimizer/workflows/build/main/希沃一体机优化工具.zip)

或前往 [Actions 页面](https://github.com/fengjian868/seewon-optimizer/actions) 手动选择某次运行下载 artifact。

## 使用

1. 下载 exe 后放到任意目录
2. 同级会自动创建文件夹（首次运行）：
   - `壁纸/` — 放壁纸图片
3. 双击 `希沃一体机优化工具.exe`，授权 UAC 后即可使用

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
