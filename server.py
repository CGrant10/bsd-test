import argparse, base64, hashlib, hmac, json, secrets, sqlite3, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DB = ROOT / 'community_assistance.db'
PUBLIC = ROOT / 'public'
SESSIONS = {}
MANAGER_EMAIL = 'admin@bsd7.local'
MANAGER_PASSWORD = 'CommunityAssist7!'

def now(): return int(time.time())

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    return con

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000)
    return base64.b64encode(salt).decode() + '$' + base64.b64encode(digest).decode()

def verify_password(password, stored):
    try:
        s, d = stored.split('$', 1)
        salt = base64.b64decode(s); expected = base64.b64decode(d)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 210000)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False

def init_db():
    con = db()
    con.executescript('''
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      email TEXT NOT NULL UNIQUE COLLATE NOCASE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'community' CHECK(role IN ('community','creator','approver','admin')),
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS alerts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      child_name TEXT,
      age TEXT,
      description TEXT NOT NULL,
      last_known TEXT,
      vehicle TEXT,
      photo_url TEXT,
      law_agency TEXT NOT NULL,
      law_phone TEXT NOT NULL,
      case_number TEXT,
      status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','resolved')),
      created_by INTEGER NOT NULL,
      approved_by INTEGER,
      created_at INTEGER NOT NULL,
      approved_at INTEGER,
      resolved_at INTEGER,
      FOREIGN KEY(created_by) REFERENCES users(id),
      FOREIGN KEY(approved_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS audit(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      action TEXT NOT NULL,
      alert_id INTEGER,
      detail TEXT,
      created_at INTEGER NOT NULL
    );
    ''')
    con.commit(); con.close()

def create_user(name, email, password, role='community'):
    con = db()
    cur = con.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)',
                      (name, email.lower().strip(), hash_password(password), role, now()))
    uid = cur.lastrowid
    con.commit(); con.close(); return uid

def safe_user(r):
    return {k:r[k] for k in ['id','name','email','role','created_at']}

def bootstrap_demo():
    con = db()
    row = con.execute('SELECT id,role FROM users WHERE email=?',(MANAGER_EMAIL,)).fetchone()
    if row:
        con.execute("UPDATE users SET role='admin' WHERE id=?",(row['id'],))
        con.commit()
        con.close()
    else:
        con.close()
        create_user('Riley Keplin',MANAGER_EMAIL,MANAGER_PASSWORD,'admin')

def audit(uid, action, alert_id=None, detail=''):
    con = db(); con.execute('INSERT INTO audit(user_id,action,alert_id,detail,created_at) VALUES(?,?,?,?,?)',(uid,action,alert_id,detail,now())); con.commit(); con.close()

def pub(r):
    return {k:r[k] for k in ['id','title','child_name','age','description','last_known','vehicle','photo_url','law_agency','law_phone','case_number','status','created_at','approved_at','resolved_at']}

class H(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        rel = urlparse(path).path.lstrip('/') or 'index.html'
        return str((PUBLIC/rel).resolve())
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Cache-Control','no-store'); super().end_headers()
    def body(self):
        n=int(self.headers.get('Content-Length','0') or '0')
        if n>2000000: raise ValueError('too large')
        return json.loads((self.rfile.read(n) if n else b'{}').decode() or '{}')
    def j(self,obj,code=200):
        b=json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def sess(self):
        a=self.headers.get('Authorization',''); t=a[7:] if a.startswith('Bearer ') else ''; s=SESSIONS.get(t)
        if not s or s['expires']<=now(): return None
        con=db(); r=con.execute('SELECT id,name,email,role FROM users WHERE id=?',(s['id'],)).fetchone(); con.close()
        if not r: return None
        s.update({'id':r['id'],'name':r['name'],'email':r['email'],'role':r['role']})
        return s
    def need(self,roles=None):
        s=self.sess()
        if not s: self.j({'error':'authentication required'},401); return None
        if roles and s['role'] not in roles: self.j({'error':'not authorized'},403); return None
        return s
    def do_GET(self):
        p=urlparse(self.path).path
        if p=='/api/health': return self.j({'ok':True,'service':'BSD7 Community Assistance','time':now()})
        if p=='/api/me':
            s=self.need(); return self.j({'user':s}) if s else None
        if p=='/api/alerts':
            s=self.need();
            if not s:return
            con=db(); rows=con.execute("SELECT * FROM alerts WHERE status IN ('active','resolved') ORDER BY created_at DESC LIMIT 50").fetchall(); con.close(); return self.j({'alerts':[pub(r) for r in rows]})
        if p=='/api/admin/alerts':
            s=self.need(['creator','approver','admin']);
            if not s:return
            con=db(); rows=con.execute('SELECT * FROM alerts ORDER BY created_at DESC LIMIT 100').fetchall(); con.close(); return self.j({'alerts':[pub(r) for r in rows]})
        if p=='/api/admin/users':
            s=self.need(['admin']);
            if not s:return
            con=db(); rows=con.execute("SELECT id,name,email,role,created_at FROM users WHERE role IN ('creator','approver','admin') ORDER BY created_at DESC LIMIT 100").fetchall(); con.close(); return self.j({'users':[safe_user(r) for r in rows]})
        return super().do_GET()
    def do_POST(self):
        p=urlparse(self.path).path
        try:b=self.body()
        except Exception:return self.j({'error':'invalid request'},400)
        if p=='/api/register':
            name=str(b.get('name','')).strip(); email=str(b.get('email','')).strip(); pw=str(b.get('password',''))
            if len(name)<2 or '@' not in email or len(pw)<10:return self.j({'error':'name, valid email, and password of at least 10 characters required'},400)
            try:uid=create_user(name,email,pw)
            except sqlite3.IntegrityError:return self.j({'error':'email already registered'},409)
            t=secrets.token_urlsafe(32); SESSIONS[t]={'id':uid,'name':name,'email':email.lower(),'role':'community','expires':now()+1209600}; audit(uid,'register'); return self.j({'token':t,'user':SESSIONS[t]},201)
        if p=='/api/login':
            email=str(b.get('email','')).strip().lower(); pw=str(b.get('password','')); con=db(); r=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
            if not r or not verify_password(pw,r['password_hash']):return self.j({'error':'invalid email or password'},401)
            t=secrets.token_urlsafe(32); SESSIONS[t]={'id':r['id'],'name':r['name'],'email':r['email'],'role':r['role'],'expires':now()+1209600}; audit(r['id'],'login'); return self.j({'token':t,'user':SESSIONS[t]})
        if p=='/api/logout': return self.j({'ok':True})
        if p=='/api/admin/alerts':
            s=self.need(['creator','admin']);
            if not s:return
            desc=str(b.get('description','')).strip(); agency=str(b.get('law_agency','')).strip(); phone=str(b.get('law_phone','')).strip()
            if not desc or not agency or not phone:return self.j({'error':'description, investigating agency and public contact number are required'},400)
            con=db(); cur=con.execute('''INSERT INTO alerts(title,child_name,age,description,last_known,vehicle,photo_url,law_agency,law_phone,case_number,status,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',('Community Assistance Request',b.get('child_name'),b.get('age'),desc,b.get('last_known'),b.get('vehicle'),b.get('photo_url'),agency,phone,b.get('case_number'),'pending',s['id'],now())); aid=cur.lastrowid; con.commit(); con.close(); audit(s['id'],'alert_submitted',aid,'Submitted for approval'); return self.j({'ok':True,'alert_id':aid,'status':'pending'},201)
        if p=='/api/admin/users':
            s=self.need(['admin']);
            if not s:return
            name=str(b.get('name','')).strip(); email=str(b.get('email','')).strip(); pw=str(b.get('password','')); role=str(b.get('role','')).strip()
            if role not in ('creator','approver','admin'):return self.j({'error':'choose creator, approver, or admin permission'},400)
            if len(name)<2 or '@' not in email or len(pw)<10:return self.j({'error':'name, valid email, and password of at least 10 characters required'},400)
            try:uid=create_user(name,email,pw,role)
            except sqlite3.IntegrityError:return self.j({'error':'email already registered'},409)
            audit(s['id'],'authorized_user_created',None,f'{email.lower()} as {role}')
            return self.j({'ok':True,'user':{'id':uid,'name':name,'email':email.lower().strip(),'role':role,'created_at':now()}},201)
        if p.startswith('/api/admin/alerts/') and p.endswith('/approve'):
            s=self.need(['approver','admin']);
            if not s:return
            aid=int(p.split('/')[4]); con=db(); con.execute("UPDATE alerts SET status='active',approved_by=?,approved_at=? WHERE id=?",(s['id'],now(),aid)); con.commit(); con.close(); audit(s['id'],'alert_approved_and_activated',aid,'Push delivery hook invoked'); return self.j({'ok':True,'status':'active','push':'queued-demo'})
        if p.startswith('/api/admin/alerts/') and p.endswith('/resolve'):
            s=self.need(['approver','admin']);
            if not s:return
            aid=int(p.split('/')[4]); con=db(); con.execute("UPDATE alerts SET status='resolved',resolved_at=? WHERE id=?",(now(),aid)); con.commit(); con.close(); audit(s['id'],'alert_resolved',aid,'All-clear hook invoked'); return self.j({'ok':True,'status':'resolved','push':'all-clear-queued-demo'})
        return self.j({'error':'not found'},404)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=8080); ap.add_argument('--demo',action='store_true'); ap.add_argument('--create-admin',nargs=3); a=ap.parse_args(); init_db()
    if a.create_admin:
        n,e,p=a.create_admin; create_user(n,e,p,'admin'); print('Admin created:',e); return
    if a.demo:
        bootstrap_demo(); print(f'MANAGER: {MANAGER_EMAIL} / {MANAGER_PASSWORD}')
    print(f'BSD #7 Community Assistance: http://localhost:{a.port}')
    print(f'Phone on same Wi-Fi: http://YOUR-LAPTOP-IP:{a.port}')
    ThreadingHTTPServer(('0.0.0.0',a.port),H).serve_forever()
if __name__=='__main__': main()
