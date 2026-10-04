"""One-shot local preparation; no production writer or network operations."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT.parent.parent / 'review/market-report-foundation-20261004/evidence'
EVIDENCE.mkdir(parents=True, exist_ok=True)
paths = list(ROOT.glob('reports/**/*.json')) + list(ROOT.glob('data/**/*')) + list(ROOT.glob('images/reports/**/*')) + [ROOT/'reports.json']
baseline = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
(EVIDENCE/'production-baseline.json').write_text(json.dumps(baseline, indent=2), encoding='utf-8')
source = Path('C:/Users/atsuk/.codex/attachments/dcbacbc0-3d11-4d9d-904b-2b996f46a4dd/貼り付けたテキスト.txt')
(ROOT/'docs/project-control/SOURCE_SPEC.md').write_text(source.read_text(encoding='utf-8-sig'), encoding='utf-8')
order = '''## 正式トランザクション順序

1. 明示されたReportContext（対象日・時刻・report_id・revision）とimmutable MarketDataSnapshotを固定する。
2. 指定ChatGPT会話へ本文原文全文を表示し、原文を保持する。
3. 同じ本文・snapshot・report_id・revisionの図解を表示する。
4. 同一Google Docs fileIdへ本文を保存する。
5. 保存先と同じfileIdを再読取し、限定normalizationと前後diffで全文一致を検証する。
6. 対応PNGのDrive実在、filename、bytes、本文・snapshot・版の一致を検証する。
7. Publication Manifestを生成する（READY_FOR_PUBLICATION）。receiptは公開前bundleに含めない。
8. 同じManifestのcanonical / reports.json / latest / dashboardの整合とrevision後退防止を検証し、GitHubへ登録する。
9. 同一commit SHAのGitHub Actions成功とGitHub Pages deploymentを確認する。
10. 公開DOMの本文・市場表・PNG・操作・timeout・mobile・consoleを検証する。
11. 公開検証後だけPublication Receiptを生成し、Manifest・Git SHA・Pages・DOM証拠へ結び付ける。
12. 全証拠が揃った場合だけVERIFIEDとする。失敗は停止し、外部効果不明はUNKNOWNのまま再試行前に照合する。

'''
annex = '''
## 2026-10-04 Manifest / Receipt契約確定（SC-01〜03解消）

Publication Manifestは公開前の固定契約。必須fieldは `manifest_id`, `report_id`, `report_date`, `report_time`, `revision`, `body_hash`, `snapshot_id`, `drive_file_id`, `drive_url`, `png_file_id`, `png_filename`, `created_at`。状態はREADY_FOR_PUBLICATION。PNG欠落・不一致ではManifest FAILとし、新規GitHub登録／Pages公開の許可を発行しない。

Publication Receiptは公開後の結果証拠。必須fieldは `report_id`, `revision`, `manifest_id`, `manifest_hash`, `git_commit_sha`, `pages_deployment_id`, `published_at`, `verified_at`, `portal_url`, `dom_validation_status`, `final_status`。PUBLISHED / VERIFIED / FAILED / UNKNOWNを区別する。公開前bundleには含めず、全公開検証後に生成する。既存過去receiptは読取互換として保持し、一括変換・削除しない。

ReportContextは入口で一度生成してreadonly、retryでも同一値を再使用する。report_date/report_timeは明示入力。unknown cronはfail closed。土日は新規発行なし。historical/recoveryは明示modeと対象日時で別扱い。attempt_id/execution_started_at/saved_at/published_at/verified_atはExecutionContextへ分離する。市場取得（月〜土06:30等）は発行とは独立する。

Snapshotは同一report_id・revision・data_cutoffに固定する。本文生成後のlatest混入・Docs/PNG/JSON/portalでの再取得は禁止。新価格は新revision。ReportObjectはreport_id/report_date/report_time/revision/snapshot_id/title/full_text/sections/market_data_table/markets/previous_report_id/statusを持つ。数値とdisplayText、観測directionとoutlook、0/null/UNAVAILABLE/STALE/N/Aを区別する。

全文照合で許すnormalizationはCRLF/LFと末尾単一改行のみを初期実装とする。Drive由来空行は別途根拠と限定ruleが承認されるまで自動吸収しない。句点・文章・表現・数値変更は不一致。normalize前後diffを保持する。

2026-10-02_21-00はcanonicalIdentity=UNRESOLVED、publicationStatus=UNVERIFIED、reviewStatus=NEEDS_REVIEWとして保全する。OLD削除、NEW自動統一、canonical/receipt書換え、PNG再生成は禁止。

今回の実装はA→B→D→Cと回帰確認まで。E〜HのPublisher / Projection / Portal / Scheduler再編・本番データ変更・push/deployは実施しない。過去v1.7等の順序記述は履歴であり、本節の現行契約を優先する。
'''
for old in (ROOT/'docs/project-control/spec-backups').glob('*.md'):
    s = old.read_text(encoding='utf-8-sig')
    s = re.sub(r'## 正式トランザクション順序\n.*?(?=## |### |本文・図解の表示)', order, s, count=1, flags=re.S)
    s = s.replace('GitHub登録、publication receipt、ポータル公開・再読込確認', 'Publication Manifest、GitHub登録、Actions、ポータル公開・再読込確認、Publication Receipt')
    s = s.replace('GitHub、receipt、ポータル', 'Manifest、GitHub、Actions、ポータル検証、Receipt')
    s = s.replace('FR-07: GitHub成功後だけpublication receiptを作成する。', 'FR-07: Drive本文とPNG検証後にManifestを固定し、GitHub登録へ進む。')
    s = s.replace('FR-08: receipt成功後だけポータル公開へ進む。', 'FR-08: Actions、Pages、公開DOM検証後だけReceiptを作成する。')
    s = s.replace('GitHub→receipt→portal→公開再読取', 'Manifest→GitHub→Actions→Pages→公開DOM検証→Receipt→VERIFIED')
    s = s.replace('GITHUB_REGISTERED → RECEIPT_CREATED → PORTAL_PUBLISHED → VERIFIED', 'PNG_VERIFIED → MANIFEST_READY → GITHUB_REGISTERED → ACTIONS_PASSED → PORTAL_PUBLISHED → DOM_VERIFIED → RECEIPT_CREATED → VERIFIED')
    s = s.replace('GitHub成功前にreceiptを作らない。', '公開DOM検証前にReceiptを作らない。')
    s = s.replace('GitHub登録 → receipt作成 → portal公開 → 公開ページ再読取', 'Manifest生成 → GitHub登録 → Actions → Pages → 公開ページ再読取 → Receipt作成')
    s = s.replace('GitHub失敗時はreceiptを作らない。receipt失敗時はportal完了扱いにしない。', 'GitHub/Actions/Pages/DOM検証失敗時は検証済Receiptを作らない。Receipt失敗時はVERIFIEDにしない。外部効果不明はUNKNOWNとする。')
    s = re.sub(r'publication receiptには最低限.*?検証する。', 'Drive保存証拠はPublication Manifestのdrive_file_id/drive_url/body_hashへ保持する。本文原文と同一fileIdからの全文読戻し、文書タイトル、report_idを検証する。Receiptは公開結果を記録し、本文保存証拠だけでVERIFIEDにしない。', s)
    s = s.replace('publication receiptを含む公開バンドル生成', 'Publication Manifestを含む公開バンドル生成（Receiptを含めない）')
    s = s.replace('Pagesデプロイ → 公開DOM再読込確認。', 'Pagesデプロイ → 公開DOM再読込確認 → Publication Receipt生成 → VERIFIED。')
    s = s.replace('作業ツリー上でreceiptを先に生成しても、GitHub登録・公開が成功するまで公開完了とはしない。', '公開前はManifestだけを生成する。Receiptは同じGit SHAの公開DOM検証後に生成する。')
    destination = ROOT/'docs'/old.name
    destination.write_text(s.rstrip()+'\n'+annex, encoding='utf-8')
    import difflib
    (EVIDENCE/(old.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8-sig').splitlines(True), destination.read_text(encoding='utf-8').splitlines(True))), encoding='utf-8')
print('baseline files:', len(baseline), 'formal drafts:', 5)
