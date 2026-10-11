"""Allowlist + narrow leak checks; not a copyright or semantic certificate."""
import argparse
import ast
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

RULES = [
    ('user-home', re.compile(r'[A-Za-z]:[\\/]Users[\\/][^\\/\s"<>]+')),
    ('key-shape', re.compile(r'\bsk-[A-Za-z0-9_-]{20,}')),
    ('private-key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
    ('inline-secret', re.compile(r'''[,{]\s*["'](?:api_key|secret|password|token)["']\s*:\s*["'][^"']+["']''', re.I)),
]

def content_findings(name, raw):
    findings = []
    try:
        text = raw.decode('utf-8')
    except UnicodeError:
        return [('non-utf8', name)]
    for label, rule in RULES:
        for match in rule.finditer(text):
            # Locations only; never echo potential secrets.
            findings.append((label, f'{name}:{text.count(chr(10), 0, match.start()) + 1}'))
    if name.endswith('.py'):
        tree = ast.parse(text)
        for node in ast.walk(tree):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and not node.level else []
            for module in modules:
                first = (module or '').split('.')[0]
                if first and first not in sys.stdlib_module_names and first != 'book_distiller':
                    findings.append(('external-import', f'{name}:{node.lineno}'))
    return findings

def check(root, archive=None):
    root = Path(root)
    names = set(json.loads((root/'tools/release-files.json').read_text(encoding='utf-8')))
    findings, source = [], {}
    actual = set()
    for path in root.rglob('*'):
        name = path.relative_to(root).as_posix()
        if '.git' in path.relative_to(root).parts or '__pycache__' in path.relative_to(root).parts:
            continue
        if path.is_symlink():
            findings.append(('symlink',name)); continue
        if path.is_file():
            actual.add(name)
            if name in names:
                source[name] = path.read_bytes()
                findings.extend(content_findings(name,source[name]))
    findings += [('unlisted', n) for n in sorted(actual-names)]
    findings += [('missing', n) for n in sorted(names-actual)]
    if archive:
        wheel = Path(archive).suffix == '.whl'
        with zipfile.ZipFile(archive) as z:
            packed = {}
            seen = set()
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                n = entry.filename
                if n in seen:
                    findings.append(('archive-duplicate',n))
                seen.add(n)
                p = PurePosixPath(n)
                if p.is_absolute() or '..' in p.parts or '\\' in n:
                    findings.append(('archive-path',n)); continue
                raw = z.read(entry)
                if wheel:
                    if len(p.parts) == 2 and p.parts[0] == 'book_distiller-0.2.0.dist-info' and p.name in {'METADATA','WHEEL','entry_points.txt','top_level.txt','RECORD','LICENSE','NOTICE.md'}:
                        findings.extend(content_findings(n,raw)); continue
                    relative = n
                else:
                    if not n.startswith('book-distiller-0.2.0-source/'):
                        findings.append(('archive-root',n)); continue
                    relative = n.split('/',1)[1]
                packed[relative] = raw
                if relative not in source or raw != source[relative]:
                    findings.append(('archive-content',n))
            expected = {n for n in names if n.startswith('book_distiller/')} if wheel else names
            findings += [('archive-missing',n) for n in sorted(expected-set(packed))]
            findings += [('archive-extra',n) for n in sorted(set(packed)-expected)]
            if wheel:
                for n in ('METADATA','WHEEL','entry_points.txt','LICENSE','NOTICE.md'):
                    path='book_distiller-0.2.0.dist-info/'+n
                    if path not in seen:
                        findings.append(('wheel-metadata-missing',path))
                    elif n in ('LICENSE','NOTICE.md') and z.read(path) != source[n]:
                        findings.append(('archive-license',path))
    return {'files':len(names),'archive':bool(archive),'findings':findings,
            'sha256':{n:hashlib.sha256(raw).hexdigest() for n,raw in sorted(source.items())},
            'limits':'Only this allowlisted tree/archive; not Git history, semantic quality, comprehensive secret detection or legal clearance.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); p.add_argument('--archive',type=Path)
    p.add_argument('--json-out',type=Path); args=p.parse_args()
    result=check(args.root,args.archive)
    if args.json_out:
        args.json_out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for rule,location in result['findings']:
        print(rule + ': ' + location)
    print(f"{'FAIL' if result['findings'] else 'PASS'}: {result['files']} allowlisted files; {len(result['findings'])} findings")
    return 1 if result['findings'] else 0

if __name__=='__main__':
    raise SystemExit(main())
