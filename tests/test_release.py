import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]

def copy_source(root):
    names=json.loads((SOURCE/'tools/release-files.json').read_text(encoding='utf-8'))
    for name in names:
        target=root/name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(SOURCE/name,target)

class ReleaseGate(unittest.TestCase):
    def test_wheel_keeps_matching_license_and_notice(self):
        with tempfile.TemporaryDirectory() as directory:
            clean=Path(directory)/'source'; copy_source(clean)
            for changed in (False, True):
                archive=Path(directory)/('altered.whl' if changed else 'valid.whl')
                with zipfile.ZipFile(archive,'w') as z:
                    for p in (SOURCE/'book_distiller').glob('*.py'):
                        z.write(p,'book_distiller/'+p.name)
                    for n in ('METADATA','WHEEL','entry_points.txt'):
                        z.writestr('book_distiller-0.2.0.dist-info/'+n,'synthetic metadata\n')
                    for n in ('LICENSE','NOTICE.md'):
                        raw=(SOURCE/n).read_bytes()
                        if changed and n=='NOTICE.md': raw=b'altered credit\n'
                        z.writestr('book_distiller-0.2.0.dist-info/'+n,raw)
                result=subprocess.run([sys.executable,'-B',str(clean/'tools/check_release.py'),'--archive',str(archive)],capture_output=True,text=True,encoding='utf-8')
                self.assertEqual(result.returncode,1 if changed else 0,result.stdout+result.stderr)
                if changed: self.assertIn('archive-license',result.stdout)
    def test_unlisted_file_and_user_home_are_detected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            copy_source(root)
            (root/'unexpected.json').write_text('{}',encoding='utf-8')
            path='C:' + chr(92) + 'Users' + chr(92) + 'SyntheticReader' + chr(92) + 'private'
            with (root/'README.md').open('a',encoding='utf-8') as out:
                out.write('\n'+path+'\n')
            result=subprocess.run([sys.executable,'-B',str(root/'tools/check_release.py')],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,1)
            self.assertIn('unlisted: unexpected.json',result.stdout)
            self.assertIn('user-home: README.md',result.stdout)
            self.assertNotIn('SyntheticReader',result.stdout)

if __name__=='__main__':
    unittest.main()
