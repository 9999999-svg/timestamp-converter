# Unix 时间戳转换器

把日志或接口中的 Unix 秒/毫秒转换为日期，或把带时区偏移量的日期转换为时间戳。批量预览并导出 CSV，精确保留到微秒，支持负时间戳。

## 下载

[Windows x64 EXE](https://github.com/9999999-svg/timestamp-converter/releases/download/v1.0.0/TimestampConverter.exe) · [Python 源码 ZIP](https://github.com/9999999-svg/timestamp-converter/releases/download/v1.0.0/timestamp-converter-source-v1.0.0.zip) · [SHA-256 清单](https://github.com/9999999-svg/timestamp-converter/releases/download/v1.0.0/SHA256SUMS.txt)

EXE 约 12.5 MiB，内含 Python/Tcl/Tk，无需安装 Python，未签名。全部功能免费；自有代码 MIT，第三方许可随包提供。

## 使用

双击 EXE，每行输入一个值或加载 UTF-8/BOM 文本，选择转换方向、秒/毫秒及显示时区，点击「转换 / 预览」或「导出 CSV」。默认按秒转换为 UTC 日期；空白行跳过，每个错误单独显示。

`0` 秒对应 `1970-01-01T00:00:00.000000Z`；`-1` 毫秒对应 `1969-12-31T23:59:59.999000Z`。日期输入例如 `1970-01-01T08:00:00+08:00`，与 Unix 起点相同。

```powershell
python timestamp_converter.py "时间戳.txt" --unit milliseconds --offset +08:00
TimestampConverter.exe "日期.txt" --direction to-timestamp --unit seconds --csv "结果.csv"
python timestamp_converter.py "时间戳.txt" --offset=-05:30
```

命令行输出 JSON 报告：退出码 0 表示全部转换成功、1 表示至少一行错误、2 表示操作失败、130 表示键盘中断。CSV 含全部结果及错误，拒绝覆盖已有文件；负偏移参数使用 `--offset=-05:30` 写法。不带参数打开窗口。

## 必要限制

- 时间戳单位必须明确，秒最多 6 位小数、毫秒最多 3 位小数；不自动猜单位，不接受指数或 NaN/Infinity。
- 日期格式为 `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` 或含 `±HH:MM` 偏移量；也支持日期与时间之间一个空格。无偏移日期、无秒日期及闰秒拒绝。
- 时区仅支持 UTC/Z 或固定偏移量，如 `+08:00`；不包含 IANA 历史时区或夏令时规则。日期范围为 Python 支持的公历 1–9999 年，偏移后的时间也须在范围内。
- 输入最多 1 MiB/10000 行，单个非空值最多 200 字符；窗口最多预览 1000 行，CSV 包含全部行。
- CSV 为 UTF-8 BOM，文本字段开头的 `= + - @` 会加单引号，保留文字显示。源文本保留；路径中的链接及目录联接拒绝。
- 正常失败或取消会清理临时 CSV，强制结束可能留下 `.timestamp-*.tmp`。Unix 时间不计闰秒；本工具不与在线时间服务同步。

## 源码和构建

Python 3.11+，仅使用标准库与 Tkinter。使用已有虚拟环境可直接运行；构建需要 PyInstaller 6.21.0：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install pyinstaller==6.21.0
.venv\Scripts\python.exe build.py
```

生成 `dist/TimestampConverter.exe`。依赖版本、体积和卸载见 [DEPENDENCIES.md](DEPENDENCIES.md)，第三方许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。便携版删除 EXE 即可卸载；自己建立的虚拟环境可在关闭程序后删除。

## 自愿赞助

下载、源码和全部功能免费，赞助完全自愿。

<img src="assets/donate-wechat.png" alt="自愿微信赞助二维码" width="280">
