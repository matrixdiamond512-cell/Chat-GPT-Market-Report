"""Single offline intake/publisher candidate; cannot write Drive, GitHub, or Pages.

Input is an exported source bundle, never a prompt. Missing inputs are held.
Only logs/report-delivery-shadow is writable. Local checks are not live evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone

from report_source_contract import validate_saved_body, title_for
from sync_latest_report_publication import validate_sop_body
from reporting.publication_evidence import validate_receipt, verify_slot_evidence
from reporting.gates import validate_png
from verify_zero_cost_delivery import check as cost_gate

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def load(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError('ARTIFACT_MUST_BE_OBJECT:' + path.name)
    return obj


def safe_file(directory: Path, name: str) -> Path:
    path = (directory / name).resolve()
    if not path.is_relative_to(directory.resolve()):
        raise ValueError('ARTIFACT_PATH_ESCAPE')
    return path


def shadow_root(root: Path) -> Path:
    target = root / 'logs/report-delivery-shadow'
    # Do not follow a pre-existing logs symlink/junction out of the checkout.
    if target.resolve() != root.resolve() / 'logs/report-delivery-shadow':
        raise ValueError('SHADOW_PATH_ESCAPE')
    target.mkdir(parents=True, exist_ok=True)
    return target


def validate_slot(report_id: str, root: Path) -> tuple[str, str]:
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}_(?:08|12|16|21)-00', report_id):
        raise ValueError('EXPLICIT_REPORT_ID_REQUIRED')
    day, slot = report_id.split('_')
    parsed = date.fromisoformat(day)
    schedule = load(root / 'config/report_schedule.json')
    category = 'weekday' if parsed.weekday() < 5 else 'saturday' if parsed.weekday() == 5 else 'sunday'
    slot = slot.replace('-', ':')
    if slot not in schedule[category]['publicationSlots']:
        raise ValueError('SLOT_NOT_CONFIGURED')
    return day, slot


def validate_bundle(report_id: str, source: Path, root: Path, work: Path, source_bytes: dict[str, bytes]) -> tuple[dict, dict]:
    def read(name: str) -> dict:
        obj = json.loads(source_bytes[name].decode('utf-8-sig'))
        if not isinstance(obj, dict):
            raise ValueError('ARTIFACT_MUST_BE_OBJECT:' + name)
        return obj
    report = read('report.json')
    day, slot = validate_slot(report_id, root)
    if (report.get('date'), report.get('time'), report.get('title')) != (day, slot, title_for(day, slot)):
        raise ValueError('SOURCE_IDENTITY_MISMATCH')
    if type(report.get('revision')) is not int or report['revision'] < 1:
        raise ValueError('SOURCE_REVISION_REQUIRED')
    if report.get('bodyHash') != digest(str(report.get('fullText', '')).encode('utf-8')):
        raise ValueError('SOURCE_BODY_HASH_MISMATCH')
    validate_saved_body(report)
    validate_sop_body(report)
    if slot == '08:00':
        # Reuse the actual 28x5/date/semantics/provenance checker, with isolated outputs.
        safe_file(work, 'input-index.json').write_bytes(encoded([report]))
        safe_file(work, 'input-latest.json').write_bytes(encoded({'latestReport':report}))
        result = subprocess.run([sys.executable, str(Path(__file__).with_name('verify_morning_report_qa.py')),
            '--date', day, '--allow-historical', '--reports', str(work / 'input-index.json'),
            '--latest-report', str(work / 'input-latest.json'), '--output', str(safe_file(work, 'morning-qa.json'))],
            capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            raise ValueError('MORNING_CONTENT_QA_BLOCKED:see morning-qa.json')
    receipt = read('receipt.json')
    validate_receipt(receipt, report)
    drive = read('drive-file.json')
    expected_parent = read('bundle.json').get('bodyMonthFolderId')
    if not expected_parent or drive.get('parents') != [expected_parent]:
        raise ValueError('MONTH_FOLDER_BINDING_MISSING')
    if drive.get('id') != report.get('sourceDocument', {}).get('id'):
        raise ValueError('DRIVE_SOURCE_ID_MISMATCH')
    if drive.get('mimeType') != 'application/vnd.google-apps.document':
        raise ValueError('DRIVE_SOURCE_MIME_MISMATCH')
    evidence_copy = safe_file(work, 'source-evidence.json')
    evidence_copy.write_bytes(source_bytes['evidence.json'])
    checked = verify_slot_evidence(report, evidence_copy, drive, str(report.get('sourceRevisionId') or ''))
    for key in ('reportId','revision','bodyHash','documentRevisionId','snapshotId','evidenceId','contextHash','snapshotHash','savedAt'):
        if checked.get(key) != receipt.get(key):
            raise ValueError('SOURCE_RECEIPT_BINDING_MISMATCH:' + key)
    image = source_bytes['infographic.png']
    validate_png(image)
    manifest = read('infographic-manifest.json')
    expected = {'report_id':report_id, 'revision':report['revision'],
                'snapshot_id':receipt['snapshotId'], 'body_hash':report['bodyHash'],
                'png_sha256':digest(image), 'png_filename':f'マーケットレポート_{report_id}.png'}
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('INFOGRAPHIC_SOURCE_BINDING_MISMATCH')
    return report, {'receipt':receipt, 'manifest':manifest, 'image':image}


def _store(connection: sqlite3.Connection, report_id: str, revision: int, payload: dict, sources: dict[str, bytes]) -> dict:
    """Commit one immutable shadow projection and event under the same SQLite lock."""
    body = encoded(payload).decode('utf-8')
    existing = connection.execute('SELECT payload FROM artifacts WHERE report_id=? AND revision=?', (report_id, revision)).fetchone()
    if existing:
        stored = dict(connection.execute('SELECT name,content FROM source_files WHERE report_id=? AND revision=?', (report_id, revision)).fetchall())
        if stored != sources:
            raise ValueError('SHADOW_SOURCE_ARCHIVE_CONFLICT')
        if existing[0] != body:
            raise ValueError('SHADOW_ARTIFACT_CONFLICT')
        return json.loads(existing[0])
    connection.execute('INSERT INTO artifacts VALUES (?,?,?)', (report_id, revision, body))
    connection.executemany('INSERT INTO source_files VALUES (?,?,?,?)', [(report_id,revision,name,content) for name,content in sources.items()])
    connection.execute('INSERT INTO events(report_id,revision,state,observed_at) VALUES (?,?,?,?)',
        (report_id,revision,'SHADOW_STAGED',datetime.now(JST).isoformat()))
    return payload


def run(report_id: str, source: Path | None, root: Path = ROOT) -> dict:
    validate_slot(report_id, root)
    gate = cost_gate(root)
    if gate['status'] != 'PASS_LOCAL_ONLY':
        return {'status':'BLOCKED_COST_UNVERIFIED','costGate':gate}
    target = shadow_root(root)
    if source is None or not source.is_dir():
        return {'reportId':report_id,'status':'WAITING_FOR_SOURCE_ARTIFACT','mode':'shadow',
                'productionWrites':0,'reason':'No source bundle received; generation is not implemented by the importer'}
    required = ['report.json','receipt.json','drive-file.json','bundle.json','evidence.json','infographic.png','infographic-manifest.json']
    missing = [name for name in required if not safe_file(source,name).is_file()]
    if missing:
        return {'reportId':report_id,'status':'WAITING_FOR_SOURCE_ARTIFACT','missing':missing,'mode':'shadow','productionWrites':0}
    # Hash the exact bundle before locking and recheck after validation to detect concurrent editing.
    source_bytes = {name:safe_file(source,name).read_bytes() for name in required}
    original = {name:digest(content) for name,content in source_bytes.items()}
    connection = sqlite3.connect(safe_file(target, 'journal.sqlite3'), timeout=0)
    try:
        connection.execute('CREATE TABLE IF NOT EXISTS artifacts(report_id TEXT,revision INTEGER,payload TEXT,PRIMARY KEY(report_id,revision))')
        connection.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,report_id TEXT,revision INTEGER,state TEXT,observed_at TEXT)')
        connection.execute('CREATE TABLE IF NOT EXISTS source_files(report_id TEXT,revision INTEGER,name TEXT,content BLOB,PRIMARY KEY(report_id,revision,name))')
        connection.execute('BEGIN IMMEDIATE')
        work = safe_file(target, report_id)
        work.mkdir(exist_ok=True)
        report, artifacts = validate_bundle(report_id, source, root, work, source_bytes)
        if original != {name:digest(safe_file(source,name).read_bytes()) for name in required}:
            raise ValueError('SOURCE_CHANGED_DURING_VALIDATION')
        payload = {'reportId':report_id,'revision':report['revision'],'status':'SHADOW_STAGED','mode':'shadow',
            'sourceArtifactHashes':original, 'canonicalCandidate':report,
            'receiptCandidate':artifacts['receipt'], 'imageSha256':digest(artifacts['image']),
            'localStructuralAndBinding':'PASS','approvedContentQA':'BLOCKED_CANONICAL_DOCS','independentDriveReadback':'NOT_RUN',
            'infographicContentQA':'NOT_RUN','infographicVisualQA':'BLOCKED_REFERENCE_IMAGE',
            'chatOutput':'BLOCKED_CHAT_OUTPUT_CAPABILITY','driveSave':'NOT_RUN','pages':'NOT_RUN',
            'notification':'NOT_RUN','productionWrites':0,'overallAcceptance':'NOT_VERIFIED'}
        result = _store(connection, report_id, report['revision'], payload, source_bytes)
        connection.commit()
        return result
    except (ValueError, KeyError, TypeError, OSError, SystemExit) as exc:
        connection.rollback()
        return {'reportId':report_id,'status':'SHADOW_BLOCKED','reason':str(exc),'mode':'shadow','productionWrites':0}
    finally:
        connection.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report-id', required=True)
    ap.add_argument('--source-bundle', type=Path)
    args = ap.parse_args()
    try:
        result = run(args.report_id,args.source_bundle)
    except (ValueError, OSError, sqlite3.Error) as exc:
        result = {'reportId':args.report_id,'status':'SHADOW_BLOCKED','reason':str(exc),'productionWrites':0}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['status'] == 'SHADOW_STAGED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
