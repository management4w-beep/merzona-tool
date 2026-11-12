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
import os, re, sys, json, shutil, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ['Dashboard.html', 'index.html', 'accounting.html', 'procurement.html', 'designer.html', 'salary.html', 'sign.html',
         'catalog.html', 'about.html', 'privacy.html', 'acct-core.js', 'company.js', 'cad-import.js', 'pdf-text.js', 'dwg-read.js', 'version.json']
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

# ───────── 🏢 نسخة صوفية (رابط لحاله، 2026-11-12) ─────────
# طلب حمدي: "بدي يكون في رابط لحاله... يدخل مباشره على صوفيا ما يشوف ميرزونا ابدا".
# نفس الصفحات بالضبط، بس: السيرفر = برنامج صوفية (/t/sufiya على نفس سيرفرنا)، مجلدات درايف صوفية،
# اسمها ولوغوها مبنيين بالصفحة، وتخزين المتصفح مفصول (لأنو الموقعين على نفس github.io).
SERVER = 'https://merzona-server-production.up.railway.app'
SUFIYA = {
    'base': os.environ.get('SUFIYA_BASE', 'https://management4w-beep.github.io/sufiya/'),
    'remote': os.environ.get('SUFIYA_REMOTE', 'https://github.com/management4w-beep/sufiya.git'),
    'server': SERVER + '/t/sufiya',
    'drive': {'13q5WtejXrydWEeIEZ7pZoon6ocyVuX1D': '1w3Oc1It95tJfdTXJyVqrMfErCBMcblj7',   # الرئيسي (فرع الإمارات بميرزونا)
              '1tQkVAUHGy9_Tm2JZxlkkTvGUTxAWM8uS': '1CYCE3CwiGDRV5itxLCxhWE-fmf-JtMmC',   # عروض الأسعار (فرع سوريا)
              '1FL-I0R4qXdAtqLF8JgcranzKsffKgLzy': '1bxdG5pi0x9Vlkzmpc1KCXzwUYrnXnilG',   # نسخ الداشبورد الاحتياطية
              '13QxtnBbXx3SuOZIu8hA90TiD7T2CiMoC': '183xxHse1hEsPCD6rfbKbaZQbNBz6SISl'},  # الكتالوج
    'skip': ['about.html', 'privacy.html', 'googleeaa4937c2234d2e6.html'],
}
# أول سكربت بالصفحة: كل مفاتيح التخزين بتصير "sufiya:..." - هيك ولا جهاز/جلسة/مسودة بتختلط مع ميرزونا
STORAGE_SHIM = r"""<script>/* sufiya storage */(function(){try{var P='sufiya:',S=Storage.prototype,g=S.getItem,s=S.setItem,r=S.removeItem,k=S.key,L=Object.getOwnPropertyDescriptor(S,'length').get;
function own(t){var a=[],n=L.call(t);for(var i=0;i<n;i++){var x=k.call(t,i);if(x&&x.indexOf(P)===0)a.push(x.slice(P.length));}return a;}
S.getItem=function(x){return g.call(this,P+x)};S.setItem=function(x,v){return s.call(this,P+x,v)};S.removeItem=function(x){return r.call(this,P+x)};
S.key=function(i){var a=own(this);return i>=0&&i<a.length?a[i]:null};S.clear=function(){var t=this;own(t).forEach(function(x){r.call(t,P+x)})};
Object.defineProperty(S,'length',{configurable:true,get:function(){return own(this).length}});
if(window.IDBFactory){var F=IDBFactory.prototype,o=F.open,d=F.deleteDatabase;F.open=function(n,v){return v===undefined?o.call(this,P+n):o.call(this,P+n,v)};F.deleteDatabase=function(n){return d.call(this,P+n)};}
window.MZ_TENANT='sufiya';}catch(e){}})();</script>"""

def sufiya_transform(name, text, profile):
    S = SUFIYA
    text = text.replace(BASE, S['base']).replace(SERVER, S['server'])
    for a, b in S['drive'].items(): text = text.replace(a, b)
    if name.endswith('.html'):
        boot = '<script>window.MZ_COMPANY_BOOT=' + json.dumps(profile, ensure_ascii=False).replace('</', '<\\/') + ';</script>'
        # بعد سطر الترميز (charset) مباشرة - لازم يضل بأول 1024 بايت
        m = re.search(r'<meta[^>]*charset[^>]*>', text[:2000], re.I) or re.search(r'<head[^>]*>', text)
        text = text[:m.end()] + '\n' + STORAGE_SHIM + boot + text[m.end():] if m else STORAGE_SHIM + boot + text
        text = re.sub(r'<title>([^<]*)</title>', lambda t: '<title>' + t.group(1).replace('Merzona Tool', profile['nameEn']).replace('Merzona', profile['nameEn']).replace('ميرزونا', profile['nameAr']) + '</title>', text, count=1)
    return text

def build_sufiya(dest):
    sd = os.path.join(ROOT, 'tools', 'sufiya')
    profile = json.load(open(os.path.join(sd, 'profile.json'), encoding='utf8'))
    for f in PAGES:
        src = os.path.join(ROOT, f)
        if f in SUFIYA['skip'] or not os.path.exists(src): continue
        t = open(src, encoding='utf8').read()
        open(os.path.join(dest, f), 'w', encoding='utf8').write(sufiya_transform(f, t, profile))
    for d in ['fonts', 'catalog-images']:
        if os.path.isdir(os.path.join(ROOT, d)):
            shutil.rmtree(os.path.join(dest, d), ignore_errors=True); shutil.copytree(os.path.join(ROOT, d), os.path.join(dest, d))
    img = os.path.join(dest, 'img'); shutil.rmtree(img, ignore_errors=True); os.makedirs(img)
    # ولا صورة من ميرزونا: كل أسماء اللوغو القديمة = لوغو صوفية
    for n in ['logo.png', 'logo-light.png', 'logo-light-word.png', 'company-logo.png']: shutil.copy(os.path.join(sd, 'logo.png'), os.path.join(img, n))
    for n in ['logo-mark.png', 'logo-light-mark.png']: shutil.copy(os.path.join(sd, 'logo-vertical.png'), os.path.join(img, n))
    shutil.copy(os.path.join(sd, 'icon.png'), os.path.join(img, 'catalog-icon.png'))
    open(os.path.join(dest, '.nojekyll'), 'w').close()
    return profile

def run_tests():
    print('… فحوصات المحاسبة'); sh('node', 'tests/acct-core.test.js')
    print('… فحوصات قراءة المخططات (DXF / PDF / DWG)'); sh('node', 'tests/cad-import.test.js'); sh('node', 'tests/pdf-import.test.js'); sh('node', 'tests/dwg-import.test.js')
    print('… فحوصات المتصفح (المصمم، الكتالوج)')
    r = subprocess.run([sys.executable, 'tests/e2e/run_all.py'], cwd=ROOT, text=True, capture_output=True)
    print('\n'.join(l for l in r.stdout.splitlines() if 'FAIL' in l or 'نجحت' in l or 'فشل' in l))
    if r.returncode != 0: sys.exit('✗ في فحوصات فشلت - ما نزّلت شي.')

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'sufiya-build':  # بناء محلي بس (للفحص): release.py sufiya-build <مجلد>
        dest = sys.argv[2]; os.makedirs(dest, exist_ok=True); build_sufiya(dest); print('✓ انبنت نسخة صوفية:', dest); return
    if mode not in ('beta', 'prod', 'sufiya'): sys.exit(__doc__)
    if sh('git', 'rev-parse', '--abbrev-ref', 'HEAD') != 'develop': sys.exit('✗ لازم تكون على فرع develop')
    if sh('git', 'status', '--porcelain'): sys.exit('✗ في تعديلات مش محفوظة (commit) على develop')
    sh('git', 'fetch', '-q', 'origin', '+refs/heads/main:refs/remotes/origin/main')
    remote_dev = (sh('git', 'ls-remote', 'origin', 'refs/heads/develop').split() or [''])[0]
    if sh('git', 'rev-parse', 'HEAD') != remote_dev: sys.exit('✗ develop مش منزّل (git push origin develop)')
    rev = sh('git', 'rev-parse', '--short', 'HEAD')
    if mode == 'beta' or '--no-tests' not in sys.argv: run_tests()
    if mode == 'sufiya':
        # نفس النسخة يلي نزلت لميرزونا (main) بتنزل لصوفية - بمستودعها ورابطها لحالها
        tmp = tempfile.mkdtemp(prefix='sufiya-release-')
        try:
            sh('git', 'clone', '-q', '--depth', '1', SUFIYA['remote'], tmp)
            for f in os.listdir(tmp):
                if f != '.git': (shutil.rmtree if os.path.isdir(os.path.join(tmp, f)) else os.remove)(os.path.join(tmp, f))
            build_sufiya(tmp)
            sh('git', 'add', '-A', '.', cwd=tmp)
            if not sh('git', 'status', '--porcelain', cwd=tmp): print('ما في شي جديد لصوفية.'); return
            sh('git', 'commit', '-q', '-m', 'release: develop@' + rev + '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>', cwd=tmp)
            sh('git', 'push', '-q', 'origin', 'HEAD:main', cwd=tmp)
            print('✓ نزلت صوفية:', SUFIYA['base'])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return
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
