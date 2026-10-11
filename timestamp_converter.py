"""Exact Unix seconds/milliseconds and ISO-8601 offset-time conversion."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import re
import stat
import sys
import tempfile
import threading

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
MAX_INPUT = 1024 * 1024
MAX_LINES = 10000
FIELDS = ['line', 'input', 'result', 'status', 'detail']

def cancel(event):
    if event is not None and event.is_set():
        raise InterruptedError('已取消，未导出报告。')

def linked(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)

def ordinary_directory(path):
    for parent in (path, *path.parents):
        info = parent.lstat()
        if linked(info) or not stat.S_ISDIR(info.st_mode):
            raise ValueError('路径包含链接、目录联接或非文件夹。')

def fixed_offset(text):
    if text in {'UTC', 'Z'}:
        return timezone.utc
    match = re.fullmatch(r'([+-])([01]\d|2[0-3]):([0-5]\d)', text)
    if not match:
        raise ValueError('时区必须为 UTC 或明确的固定偏移量，例如 +08:00。')
    minutes = int(match[2]) * 60 + int(match[3])
    return timezone(timedelta(minutes=minutes if match[1] == '+' else -minutes))

def convert_one(value, direction, unit, offset):
    digits = 6 if unit == 'seconds' else 3
    scale = 10 ** digits
    if direction == 'from-timestamp':
        match = re.fullmatch(r'([+-]?)(\d{1,30})(?:\.(\d{1,' + str(digits) + r'}))?', value)
        if not match:
            raise ValueError('时间戳需为十进制数；秒最多 6 位小数、毫秒最多 3 位小数，不自动猜单位。')
        micros = int(match[2]) * scale + int((match[3] or '').ljust(digits, '0'))
        if match[1] == '-':
            micros = -micros
        moment = (EPOCH + timedelta(microseconds=micros)).astimezone(offset)
        return moment.isoformat(timespec='microseconds').replace('+00:00', 'Z')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)', value):
        raise ValueError('日期必须含秒及 Z/固定偏移量，例如 1970-01-01T08:00:00+08:00。')
    moment = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    delta = moment - EPOCH
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    whole, fraction = divmod(abs(micros), scale)
    result = ('-' if micros < 0 else '') + str(whole)
    if fraction:
        result += '.' + str(fraction).zfill(digits).rstrip('0')
    return result

def convert_lines(text, *, direction='from-timestamp', unit='seconds', offset='UTC', event=None):
    if direction not in {'from-timestamp', 'to-timestamp'} or unit not in {'seconds', 'milliseconds'}:
        raise ValueError('转换方向或时间戳单位无效。')
    target_offset = fixed_offset(offset)
    if len(text.encode('utf-8')) > MAX_INPUT:
        raise ValueError('输入最多 1 MiB。')
    lines = re.split(r'\r\n|\r|\n', text)
    if len(lines) > MAX_LINES + 1 or len(lines) == MAX_LINES + 1 and lines[-1].strip():
        raise ValueError('输入最多 10000 行。')
    rows, errors = [], 0
    for index, raw in enumerate(lines, 1):
        cancel(event)
        value = raw.strip()
        if not value:
            continue
        row = {'line': index, 'input': value, 'result': '', 'status': 'OK', 'detail': ''}
        try:
            if len(value) > 200:
                raise ValueError('单行输入最多 200 字符。')
            row['result'] = convert_one(value, direction, unit, target_offset)
        except (ValueError, OverflowError) as error:
            row['status'], row['detail'] = 'ERROR', str(error)
            errors += 1
        rows.append(row)
    if not rows:
        raise ValueError('请输入至少一个非空值。')
    return {'direction': direction, 'unit': unit, 'offset': offset, 'rows': rows,
        'converted': len(rows) - errors, 'errors': errors}

def read_input(source):
    path = Path(source).absolute()
    ordinary_directory(path.parent)
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode) or before.st_size > MAX_INPUT:
        raise ValueError('输入必须为普通 UTF-8/BOM 文本文件，最多 1 MiB。')
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
    with path.open('rb') as stream:
        if identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在打开时发生变化。')
        data = stream.read(MAX_INPUT + 1)
        if len(data) > MAX_INPUT or identity(os.fstat(stream.fileno())) != identity(before):
            raise OSError('输入在读取期间变化或超限。')
    if identity(path.lstat()) != identity(before):
        raise OSError('输入在读取后发生变化。')
    return data.decode('utf-8-sig', errors='strict')

def write_csv(report, output, event=None):
    target = Path(output).absolute()
    ordinary_directory(target.parent)
    if os.path.lexists(target):
        raise FileExistsError('输出已存在，请选择新 CSV 文件。')
    cancel(event)
    fd, name = tempfile.mkstemp(prefix='.timestamp-', suffix='.tmp', dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            for row in report['rows']:
                cancel(event)
                writer.writerow({key: "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value for key, value in row.items()})
            stream.flush()
            os.fsync(stream.fileno())
        cancel(event)
        if os.name == 'nt':
            os.rename(temporary, target)
        else:
            os.link(temporary, target)
            temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('Unix 时间戳转换器')
    root.geometry('960x760')
    frame = ttk.Frame(root, padding=16)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='每行一个值，明确选择秒/毫秒；日期必须带 Z 或固定时区偏移量，精度保留到微秒。').pack(anchor='w')
    source = tk.Text(frame, height=9)
    source.pack(fill='x', pady=8)
    bar = ttk.Frame(frame)
    bar.pack(fill='x', pady=8)
    directions = {'时间戳 → 日期': 'from-timestamp', '日期 → 时间戳': 'to-timestamp'}
    units = {'秒': 'seconds', '毫秒': 'milliseconds'}
    direction, unit, offset = tk.StringVar(value='时间戳 → 日期'), tk.StringVar(value='秒'), tk.StringVar(value='UTC')
    controls = [source]
    for label, variable, values in [('方向', direction, list(directions)), ('单位', unit, list(units))]:
        ttk.Label(bar, text=label).pack(side='left', padx=4)
        box = ttk.Combobox(bar, textvariable=variable, values=values, state='readonly', width=19)
        box.pack(side='left')
        controls.append(box)
    ttk.Label(bar, text='显示时区').pack(side='left', padx=8)
    entry = ttk.Entry(bar, textvariable=offset, width=12)
    entry.pack(side='left')
    controls.append(entry)
    ttk.Label(frame, text='日期输入必须带明确偏移量；显示时区设置用于时间戳转日期。').pack(anchor='w')
    preview = tk.Text(frame, height=15, wrap='none', state='disabled')
    preview.pack(fill='both', expand=True, pady=8)
    status = tk.StringVar(value='最多 1 MiB/10000 行；预览最多 1000 行。CSV 含全部结果与错误，不覆盖已有文件。')
    ttk.Label(frame, textvariable=status, wraplength=910).pack(anchor='w', pady=8)
    messages, event = queue.Queue(), threading.Event()
    state = {'busy': False, 'closing': False}
    def load():
        value = filedialog.askopenfilename()
        if value:
            try:
                text = read_input(value)
            except Exception as error:
                messagebox.showerror('读取失败', str(error))
                return
            source.delete('1.0', 'end')
            source.insert('1.0', text)
    def start(save=False):
        target = filedialog.asksaveasfilename(title='导出到新的 CSV 文件', defaultextension='.csv') if save else None
        if save and not target:
            return
        text = source.get('1.0', 'end-1c')
        kwargs = dict(direction=directions[direction.get()], unit=units[unit.get()], offset=offset.get(), event=event)
        event.clear()
        state['busy'] = True
        for control in controls:
            control.configure(state='disabled')
        stop.configure(state='normal')
        status.set('正在转换…')
        def worker():
            try:
                report = convert_lines(text, **kwargs)
                if target:
                    write_csv(report, target, event)
                    report['output'] = target
                messages.put(('ok', report))
            except Exception as error:
                messages.put(('error', str(error)))
        threading.Thread(target=worker, daemon=True).start()
    bar = ttk.Frame(frame)
    bar.pack(fill='x')
    for label, action in [('加载文本', load), ('转换 / 预览', lambda: start(False)), ('导出 CSV', lambda: start(True))]:
        button = ttk.Button(bar, text=label, command=action)
        button.pack(side='left', padx=4)
        controls.append(button)
    stop = ttk.Button(bar, text='取消', command=event.set, state='disabled')
    stop.pack(side='left', padx=4)
    def close():
        if state['busy']:
            state['closing'] = True
            event.set()
        else:
            root.destroy()
    def poll():
        try:
            kind, data = messages.get_nowait()
        except queue.Empty:
            root.after(100, poll)
            return
        state['busy'] = False
        if state['closing']:
            root.destroy()
            return
        for control in controls:
            control.configure(state='readonly' if isinstance(control, ttk.Combobox) else 'normal')
        stop.configure(state='disabled')
        preview.configure(state='normal')
        preview.delete('1.0', 'end')
        if kind == 'error':
            status.set(data)
        else:
            preview.insert('1.0', '\n'.join(f"{r['line']}: {r['input']} → {r['result'] if r['status'] == 'OK' else r['detail']}" for r in data['rows'][:1000]))
            status.set(f"成功 {data['converted']}，错误 {data['errors']}。" + ('CSV 已保存：' + data['output'] if 'output' in data else '预览完成。'))
        preview.configure(state='disabled')
        root.after(100, poll)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description='Unix 秒/毫秒与含偏移量的 ISO 日期精确转换。')
    parser.add_argument('input')
    parser.add_argument('--direction', choices=['from-timestamp', 'to-timestamp'], default='from-timestamp')
    parser.add_argument('--unit', choices=['seconds', 'milliseconds'], default='seconds')
    parser.add_argument('--offset', default='UTC')
    parser.add_argument('--csv')
    args = parser.parse_args()
    try:
        report = convert_lines(read_input(args.input), direction=args.direction, unit=args.unit, offset=args.offset)
        if args.csv:
            write_csv(report, args.csv)
        print(json.dumps(report, ensure_ascii=True))
        return 1 if report['errors'] else 0
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=True), file=sys.stderr)
        return 2

if __name__ == '__main__':
    if len(sys.argv) == 1:
        gui()
    else:
        raise SystemExit(main())
