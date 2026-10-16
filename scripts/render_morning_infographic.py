"""08:00-only source-bound HTML/PNG and existing publication-manifest adapter.

No production writes. Formal mode requires the unchanged canonical spec gate.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from reporting.morning_layout import render_html, build_manifest
from reporting.infographic import ValidationFailure
from preflight_morning_infographic import check as preflight_check


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('render', 'manifest'))
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--docs-readback', type=Path,
                        help='Required in formal mode; exact Google Docs body and document revision identity')
    parser.add_argument('--fixture', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--node', default='node')
    parser.add_argument('--browser', help='Optional local browser executable; never recorded as a path in artifacts')
    parser.add_argument('--png', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--drive-file-id')
    parser.add_argument('--drive-readback', type=Path)
    parser.add_argument('--png-filename')
    parser.add_argument('--report-output', type=Path, help='New local report copy with infographicManifest; never publishes')
    args = parser.parse_args()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        report, view = read(args.report), read(args.view)
        if not args.fixture:
            docs_readback = read(args.docs_readback) if args.docs_readback else None
            assessment = preflight_check(report, view, docs_readback=docs_readback,
                                         require_docs_readback=True)
            if assessment['status'] != 'READY_FOR_CANONICAL_VALIDATION':
                print(json.dumps({'status': 'BLOCKED', 'stage': 'input_preflight',
                                  'missing_or_unverified': assessment['missing_or_unverified']},
                                 ensure_ascii=False))
                return 1
        spec = read(args.spec) if args.spec else None
        if args.command == 'render':
            document, contract = render_html(report, view, fixture=args.fixture, spec=spec)
            if args.output.exists():
                raise ValidationFailure('OUTPUT_EXISTS')
            args.output.mkdir(parents=True)
            html_file, contract_file = args.output/'report.html', args.output/'render-contract.json'
            html_file.write_text(document, encoding='utf-8', newline='\n')
            contract_file.write_text(json.dumps(contract, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
            command = [args.node, str(Path(__file__).with_name('render_morning_png.js')),
                       '--html', str(html_file.resolve()), '--contract', str(contract_file.resolve()),
                       '--out', str((args.output/'png').resolve())]
            if args.browser:
                command += ['--browser', args.browser]
            subprocess.run(command, check=True)
        else:
            if not all((args.png, args.receipt, args.drive_file_id, args.drive_readback, args.png_filename)):
                parser.error('manifest needs --png --receipt --drive-file-id --drive-readback --png-filename')
            manifest = build_manifest(report, view, args.png.read_bytes(), read(args.receipt),
                                      args.drive_file_id, args.drive_readback.read_bytes(),
                                      args.png_filename, fixture=args.fixture, spec=spec)
            if args.output.exists() or (args.report_output and args.report_output.exists()):
                raise ValidationFailure('OUTPUT_EXISTS')
            # Exclusive creation prevents overwriting published or review artifacts.
            with args.output.open('x', encoding='utf-8') as file:
                file.write(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
            if args.report_output:
                with args.report_output.open('x', encoding='utf-8') as file:
                    file.write(json.dumps({**report, 'infographicManifest':manifest}, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps({'status': manifest['status'], 'artifact_type': manifest['artifact_type'],
                              'manifest_id': manifest['manifest_id']}))
        return 0
    except (ValidationFailure, ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'status': 'FAIL', 'reason': getattr(exc, 'reason', str(exc))}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
