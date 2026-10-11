"""Actual-file exact conversion and CSV checks for source and --exe."""
import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

def checks(executable=None):
    command = [str(executable)] if executable else [sys.executable, str(Path(__file__).with_name('timestamp_converter.py'))]
    def run(*args, code=0):
        result = subprocess.run(command + list(map(str, args)), capture_output=True, timeout=60)
        assert result.returncode == code, (args, result.returncode, result.stdout, result.stderr)
        return json.loads(result.stderr if code == 2 else result.stdout)
    with tempfile.TemporaryDirectory(prefix='时间戳-中文-') as name:
        root = Path(name)
        source, output = root / '时间戳.txt', root / '报告.csv'
        raw = '0\n-0.001\n1.123456\n\n'.encode('utf-8-sig')
        source.write_bytes(raw)
        report = run(source, '--csv', output)
        assert report['converted'] == 3 and not report['errors']
        assert [r['result'] for r in report['rows']] == ['1970-01-01T00:00:00.000000Z', '1969-12-31T23:59:59.999000Z', '1970-01-01T00:00:01.123456Z']
        data = output.read_bytes()
        assert data.startswith(b'\xef\xbb\xbf')
        rows = list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
        assert rows[1]['input'] == "'-0.001" and rows[2]['result'].endswith('01.123456Z')
        run(source, '--csv', output, code=2)
        run(source, '--csv', source, code=2)
        assert source.read_bytes() == raw and output.read_bytes() == data
        source.write_text('0\n-1\n1000.123', encoding='utf-8')
        report = run(source, '--unit', 'milliseconds', '--offset', '+08:00')
        assert [r['result'] for r in report['rows']] == ['1970-01-01T08:00:00.000000+08:00', '1970-01-01T07:59:59.999000+08:00', '1970-01-01T08:00:01.000123+08:00']
        source.write_text('1970-01-01T08:00:00+08:00\n1969-12-31T23:59:59.999Z\n1970-01-01T00:00:01.123456Z', encoding='utf-8')
        seconds = run(source, '--direction', 'to-timestamp')
        milliseconds = run(source, '--direction', 'to-timestamp', '--unit', 'milliseconds')
        assert [r['result'] for r in seconds['rows']] == ['0', '-0.001', '1.123456']
        assert [r['result'] for r in milliseconds['rows']] == ['0', '-1', '1123.456']
        source.write_text('2024-02-29T00:00:00Z\n2023-02-29T00:00:00Z\n2024-01-01T00:00:00\n2024-01-01T00:00:00+01:60\n2024-01-01T00:00:00+24:00', encoding='utf-8')
        report = run(source, '--direction', 'to-timestamp', code=1)
        assert report['converted'] == 1 and report['errors'] == 4 and report['rows'][0]['result'] == '1709164800'
        source.write_text('0\nNaN\n1e9\n0.0000001\n999999999999999999999999999999\n=1+1', encoding='utf-8')
        report = run(source, code=1)
        assert report['converted'] == 1 and report['errors'] == 5
        run(source, '--offset', 'Asia/Shanghai', code=2)
        run(source, '--offset=-24:00', code=2)
        source.write_bytes(b'\xff')
        run(source, code=2)
        source.write_bytes(b'\n' * 10001)
        run(source, code=2)
        with source.open('wb') as stream:
            stream.truncate(1024 * 1024 + 1)
        run(source, code=2)
        source.write_text(' \n', encoding='utf-8')
        run(source, code=2)
        source.write_text('0\n', encoding='utf-8')
        assert run(source, '--offset=-05:30')['rows'][0]['result'] == '1969-12-31T18:30:00.000000-05:30'
        symlink = root / '链接.txt'
        try:
            symlink.symlink_to(source)
        except OSError:
            print('SKIP: OS does not permit symlink fixture')
        else:
            run(symlink, code=2)
        if not executable:
            import timestamp_converter as tool
            event = threading.Event()
            event.set()
            try:
                tool.convert_lines('0', event=event)
            except InterruptedError:
                pass
            else:
                raise AssertionError('Cancellation ignored')
            event.clear()
            report = tool.convert_lines('0')
            original = tool.os.fsync
            def cancel_after_flush(fd):
                original(fd)
                event.set()
            tool.os.fsync = cancel_after_flush
            try:
                try:
                    tool.write_csv(report, root / 'cancelled.csv', event)
                except InterruptedError:
                    pass
                else:
                    raise AssertionError('Cancellation before publish ignored')
            finally:
                tool.os.fsync = original
            assert not (root / 'cancelled.csv').exists() and not list(root.glob('.timestamp-*.tmp'))
        print('PASS: actual exact seconds/milliseconds round trips, negative epoch/offset/leap day, CSV/BOM/formula guard, errors/limits/no overwrite/source unchanged', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    checks(args.exe)
