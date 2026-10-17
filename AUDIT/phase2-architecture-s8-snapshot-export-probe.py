"""Independent archived review/Git reconstruction and binary concurrency probes."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

repo = Path(sys.argv[1])
sys.path.insert(0, str(repo / 'src'))
from uados.project import Project
from uados.storage import evidence_files
from uados import governance as gov


def session(project, label):
    report = project.start_session(label)
    project.acknowledge(report['session'], report['report_hash'])
    return report['session']


def current(project, identity):
    report = project.refresh_session(identity)
    project.acknowledge(identity, report['report_hash'])


def command(args, cwd):
    result = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError({'command': args, 'exit': result.returncode, 'stderr': result.stderr})
    return result.stdout


def archived_review_and_clone():
    with tempfile.TemporaryDirectory(prefix='uados-s8-archive-') as directory:
        directory = Path(directory)
        root = directory / 'project'
        project = Project.initialize(root, 'Archived reviewer probe', 'Preserve unavailable prior reviews', protocol_version=1)
        author = session(project, 'Mechanical fixture author')
        (root / 'code.py').write_text('VALUE = 1\n')
        (root / 'old-review.txt').write_bytes(b'Independent binary review\r\n\xff\x00')
        (root / 'plan.txt').write_text('Original plan\n')
        task = project.add_task(author, 'Major versioned review', 'Original acceptance', 'major', ['code.py'])['task']
        gov.plan_task(project, author, task, 'Implement bounded source', 'Inspect current outputs', ['plan.txt'])
        reviewer = session(project, 'Mechanical fixture reviewer')
        project.review_task(reviewer, task, 'plan', 'approve', 'Inspect assumptions, direct bytes and exact scope independently', ['old-review.txt'])
        old = project.read()[0]['tasks'][task]['reviews'][0]['evidence'][0]
        current(project, author)
        gov.replan_task(project, author, task, 'Changed requirement explicitly supersedes prior review', description='Current acceptance and original review preserved')
        gov.plan_task(project, author, task, 'Implement revised bounded source', 'Inspect new outputs', ['plan.txt'])
        (root / 'old-review.txt').unlink()
        before = project.audit()
        exported = directory / 'exported'
        export = project.export(exported)
        shutil.copy2(repo / '.gitignore', exported / '.gitignore')
        command(['git', 'init', '--initial-branch=main'], exported)
        selected = command(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], exported).split('\x00')
        archive_retained = old['snapshot'] in selected
        command(['git', 'add', '--all'], exported)
        command(['git', '-c', 'user.name=Independent S8 fixture', '-c', 'user.email=s8-fixture@localhost', 'commit', '-m', 'Disposable archive recovery probe'], exported)
        clone = directory / 'clone'
        command(['git', 'clone', '--quiet', str(exported), str(clone)], directory)
        no_db = not (clone / '.uados/ledger.sqlite3').exists()
        rebuilt = Project.rebuild_ledger(clone)
        audit = Project(clone).audit()
        archive = clone / old['snapshot']
        exact_bytes = archive.read_bytes() == b'Independent binary review\r\n\xff\x00'
        history = Project(clone).read()[0]['tasks'][task]['reviews']
        return {'passed': before['ok'] and before['history_ok'] and archive_retained and no_db and audit['ok'] and audit['history_ok'] and exact_bytes and len(history)==1,
                'old_review_live_path_missing': not (clone / 'old-review.txt').exists(), 'git_snapshot_retained': archive_retained,
                'database_ignored_and_reconstructed': no_db, 'rebuild': rebuilt,
                'exact_binary_bytes_preserved': exact_bytes, 'before_audit': before, 'clone_audit': audit, 'export': export}


def concurrent_exact_binary_archive():
    with tempfile.TemporaryDirectory(prefix='uados-s8-concurrent-') as directory:
        root = Path(directory)
        content = b'Binary CRLF\r\n\xff\x00\xf0\x80\x80\x00' * 128
        (root / 'binary.bin').write_bytes(content)
        with ThreadPoolExecutor(max_workers=4) as pool:
            records = list(pool.map(lambda _: evidence_files(root, ['binary.bin'])[0], range(16)))
        archives = {record['snapshot'] for record in records}
        exact = len(archives)==1 and (root / next(iter(archives))).read_bytes()==content
        temporaries = list((root / '.uados/evidence/sha256').glob('.uados-write-*'))
        return {'passed': exact and not temporaries and all(record['bytes']==len(content) and record['sha256']==hashlib.sha256(content).hexdigest() for record in records),
                'parallel_registrations': len(records), 'one_exact_snapshot': exact, 'temporary_files_remaining': len(temporaries)}


results = {}
for label, function in [('archived_review_and_clone', archived_review_and_clone), ('concurrent_exact_binary_archive', concurrent_exact_binary_archive)]:
    try:
        results[label] = function()
    except Exception as error:
        results[label] = {'passed': False, 'exception': type(error).__name__, 'message': str(error)}
print(json.dumps({'independent_mechanical_fixture': True, 'results': results}, sort_keys=True, indent=2))
sys.exit(0 if all(value['passed'] for value in results.values()) else 1)
