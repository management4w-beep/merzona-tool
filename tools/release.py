#!/usr/bin/env python3
"""تنزيل النسخ بأمان (المرحلة 1 من دراسة السيستم - 2026-11-10).

الطريقة:
  1. الشغل بيصير على فرع develop (مش على main مباشرة).
  2. python3 tools/release.py beta  → بيشغّل كل الفحوصات، وإذا نجحت بينزّل نسخة develop على
     https://management4w-beep.github.io/merzona-tool/beta/  (نسخة تجريبية بشريط "نسخة تجريبية").
  3. حمدي (أو أي حدا) بيجرّب النسخة التجريبية.
  4. python3 tools/release.py prod  → بينزّل نفس النسخة المجرّبة للموقع الأساسي.

ملاحظة: النسخة التجريبية بتشتغل على نفس السيرفر ونفس درايف (بيانات حقيقية) - هي لتجربة الشاشات والتعديلات قبل
ما توصل لكل الموظفين، مش ملعب بيانات. روابط الزبائن (الكتالوج، التوقيع، الرواتب) بتضل للموقع الأساسي."""
import os, re, sys, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['Dashboard.html', 'index.html', 'accounting.html', 'procurement.html', 'designer.html', 'salary.html', 'sign.html',
         'catalog.html', 'about.html', 'privacy.html', 'acct-core.js', 'cad-import.js', 'pdf-text.js', 'version.json']
PROD_EXTRA_DIRS = ['tests', 'tools', 'fonts']
BASE = 'https://management4w-beep.github.io/merzona-tool/'
BANNER = ('<div id="mzBetaRibbon" style="position:fixed;left:8px;bottom:8px;z-index:2147483000;background:#c0392b;color:#fff;'
          'font:700 12px/1 sans-serif;padding:6px 10px;border-radius:12px;pointer-events:none;opacity:.9">🧪 نسخة تجريبية</div>')

def sh(*a, cwd=ROOT, check=True):
    r = subprocess.run(a, cwd=cwd, text=True, capture_output=True)
    if check and r.returncode != 0:
        sys.exit('✗ ' + ' '.join(a) + '\n' + r.stdout + r.stderr)
    return r.stdout.strip()

def beta_transform(name, text):
    if not name.endswith('.html'): return text
    # أدوات الموظفين جوا الداشبورد بتفتح من النسخة التجريبية كمان (روابط الزبائن بتضل للأساسي)
    for page in ['', 'designer.html', 'accounting.html', 'procurement.html']:
        for q in ("'", '"'):
            text = text.replace(BASE + page + q, BASE + 'beta/' + page + q)
    text = text.replace("const CATALOG_IMAGES_DIR = 'catalog-images/';", "const CATALOG_IMAGES_DIR = '../catalog-images/';")
    text = re.sub(r'<title>', '<title>[تجريبي] ', text, count=1)
    text = text.replace('</body>', BANNER + '\n</body>', 1) if '</body>' in text else text + BANNER
    return text

def run_tests():
    print('… فحوصات المحاسبة'); sh('node', 'tests/acct-core.test.js')
    print('… فحوصات قراءة المخططات (DXF / PDF)'); sh('node', 'tests/cad-import.test.js'); sh('node', 'tests/pdf-import.test.js')
    print('… فحوصات المتصفح (المصمم، الكتالوج)')
    r = subprocess.run([sys.executable, 'tests/e2e/run_all.py'], cwd=ROOT, text=True, capture_output=True)
    print('\n'.join(l for l in r.stdout.splitlines() if 'FAIL' in l or 'نجحت' in l or 'فشل' in l))
    if r.returncode != 0: sys.exit('✗ في فحوصات فشلت - ما نزّلت شي.')

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode not in ('beta', 'prod'): sys.exit(__doc__)
    if sh('git', 'rev-parse', '--abbrev-ref', 'HEAD') != 'develop': sys.exit('✗ لازم تكون على فرع develop')
    if sh('git', 'status', '--porcelain'): sys.exit('✗ في تعديلات مش محفوظة (commit) على develop')
    sh('git', 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
    remote_dev = (sh('git', 'ls-remote', 'origin', 'refs/heads/develop').split() or [''])[0]
    if sh('git', 'rev-parse', 'HEAD') != remote_dev: sys.exit('✗ develop مش منزّل (git push origin develop)')
    rev = sh('git', 'rev-parse', '--short', 'HEAD')
    if mode == 'beta' or '--no-tests' not in sys.argv: run_tests()
    tmp = tempfile.mkdtemp(prefix='mz-release-')
    try:
        sh('git', 'worktree', 'add', '--detach', tmp, 'origin/main')
        if mode == 'beta':
            dest = os.path.join(tmp, 'beta'); os.makedirs(dest, exist_ok=True)
            for f in PAGES:
                src = os.path.join(ROOT, f)
                if not os.path.exists(src): continue
                t = open(src, encoding='utf8').read()
                open(os.path.join(dest, f), 'w', encoding='utf8').write(beta_transform(f, t))
            shutil.rmtree(os.path.join(dest, 'img'), ignore_errors=True)
            shutil.copytree(os.path.join(ROOT, 'img'), os.path.join(dest, 'img'))
            if os.path.isdir(os.path.join(ROOT, 'fonts')):
                shutil.rmtree(os.path.join(dest, 'fonts'), ignore_errors=True)
                shutil.copytree(os.path.join(ROOT, 'fonts'), os.path.join(dest, 'fonts'))
            msg = 'beta: develop@' + rev
        else:
            for f in PAGES:
                src = os.path.join(ROOT, f)
                if os.path.exists(src): shutil.copy(src, os.path.join(tmp, f))
            for d in PROD_EXTRA_DIRS:
                if os.path.isdir(os.path.join(ROOT, d)):
                    shutil.rmtree(os.path.join(tmp, d), ignore_errors=True); shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
            msg = 'release: develop@' + rev
        sh('git', 'add', '-A', '.', cwd=tmp)
        if not sh('git', 'status', '--porcelain', cwd=tmp): print('ما في شي جديد للتنزيل.'); return
        sh('git', 'commit', '-q', '-m', msg + '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>', cwd=tmp)
        sh('git', 'push', '-q', 'origin', 'HEAD:main', cwd=tmp)
        print('✓ نزلت:', BASE + ('beta/' if mode == 'beta' else ''), '(' + msg + ')')
    finally:
        sh('git', 'worktree', 'remove', '--force', tmp, check=False)
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
