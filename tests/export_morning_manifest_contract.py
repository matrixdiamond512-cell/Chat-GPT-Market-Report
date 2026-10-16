"""Export mock-only formal manifest to exercise the existing consumer. No live IDs."""
from io import BytesIO
import json
from pathlib import Path
import sys
from PIL import Image
from morning_fixture import formal_contract_fixture
from reporting.morning_layout import render_html, build_manifest, sha

report, view, spec = formal_contract_fixture()
image=BytesIO(); Image.new('RGB',(2,2),'white').save(image,format='PNG'); png=image.getvalue()
_,contract=render_html(report,view,spec=spec)
# Mock receipt verifies only producer/consumer identity and serialization compatibility.
# It is not a browser observation and is never used for real artifacts.
receipt={'status':'PASS','artifact_type':'FORMAL_INFOGRAPHIC','numeric_validation':'PASS','renderer_status':'PASS',
         'html_sha256':contract['html_sha256'],'view_sha256':contract['view_sha256'],
         'png_sha256':sha(png),'rendered_fact_ids':contract['validation']['required_fact_ids']}
manifest=build_manifest(report,view,png,receipt,'mock-drive-file',png,
                        'マーケットレポート_2026-10-06_08-00.png',spec=spec)
Path(sys.argv[1]).write_text(json.dumps({'test_only':True,'report':report,'manifest':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
