from flask import Flask, render_template, url_for, send_from_directory
import os
import sqlite3
import gdown

# configure Flask so that the existing "a" directory is served as static
# (images can be accessed at /a/filename.jpg)
app = Flask(__name__, static_folder='a', static_url_path='/a')
app.secret_key = os.environ.get('SECRET_KEY', 'default-dev-key-12345')

DB_PATH = 'curriculum.db'
FOLDER_ID = "1sihKCSUsBlOVTmLil5yA-ZuQNT6JfF4c"

def download_curriculum_files():
    """Download curriculum files from Google Drive if they don't exist."""
    if not os.path.exists("b"):
        print("Curriculum folder 'b' not found. Downloading from Google Drive...")
        try:
            gdown.download_folder(
                id=FOLDER_ID,
                output="b",
                quiet=False
            )
            print("Download completed successfully.")
        except Exception as e:
            print(f"Error downloading from Google Drive: {e}")

def init_db():
    """Ensure the SQLite database and table exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        '''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            dept TEXT,
            subject TEXT,
            category TEXT,
            semester TEXT,
            name TEXT,
            relpath TEXT
        )
        '''
    )
    conn.commit()
    conn.close()

def rebuild_db():
    """Scan the filesystem and repopulate the database."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM files')

    root = 'b'
    if not os.path.isdir(root):
        conn.commit()
        conn.close()
        return

    for dept in os.listdir(root):
        dept_path = os.path.join(root, dept)
        if not os.path.isdir(dept_path):
            continue
        for subj in os.listdir(dept_path):
            subj_path = os.path.join(dept_path, subj)
            if not os.path.isdir(subj_path):
                continue
            for level3 in os.listdir(subj_path):
                level3_path = os.path.join(subj_path, level3)
                if not os.path.isdir(level3_path):
                    continue
                
                semester_keywords = ['خريف', 'ربيع', 'فصل', 'ترم', '202', 'عام', 'سمستر', 'فـصل']
                is_level3_semester = any(kw in level3 for kw in semester_keywords)
                
                found_level4 = False
                for level4 in os.listdir(level3_path):
                    level4_path = os.path.join(level3_path, level4)
                    if not os.path.isdir(level4_path):
                        continue
                    found_level4 = True
                    
                    if is_level3_semester:
                        cat, sem = level4, level3
                    else:
                        cat, sem = level3, level4

                    for dirpath, dirnames, filenames in os.walk(level4_path):
                        for fname in filenames:
                            rel = os.path.relpath(os.path.join(dirpath, fname), root).replace('\\', '/')
                            c.execute(
                                'INSERT INTO files (dept,subject,category,semester,name,relpath) VALUES (?,?,?,?,?,?)',
                                (dept, subj, cat, sem, fname, rel)
                            )
                
                if not found_level4:
                    if is_level3_semester:
                        cat, sem = 'عام', level3
                    else:
                        cat, sem = level3, 'عام'

                    for f in os.listdir(level3_path):
                        fpath = os.path.join(level3_path, f)
                        if os.path.isfile(fpath):
                            rel = os.path.relpath(fpath, root).replace('\\', '/')
                            c.execute(
                                'INSERT INTO files (dept,subject,category,semester,name,relpath) VALUES (?,?,?,?,?,?)',
                                (dept, subj, cat, sem, f, rel)
                            )
    conn.commit()
    conn.close()

def get_structure():
    """Read the nested structure from the database."""
    init_db()
    # Removed rebuild_db() for performance; use /refresh manually

    structure = {}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for (dept, subj, cat, sem, name, rel) in c.execute('SELECT dept, subject, category, semester, name, relpath FROM files'):
        d_node = structure.setdefault(dept, {})
        s_node = d_node.setdefault(subj, {})
        c_node = s_node.setdefault(cat, {})
        sem_node = c_node.setdefault(sem, {})
        
        sem_node.setdefault('__files__', []).append({
            'name': name,
            'url': f'/files/{rel}'
        })
    conn.close()
    return structure

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/curriculum')
def curriculum():
    structure = get_structure()
    return render_template('curriculum.html', structure=structure)

@app.route('/start-journey')
def start_journey():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    subjects_data = []
    rows = c.execute('SELECT DISTINCT subject FROM files').fetchall()
    
    for row in rows:
        name = row[0]
        weight = 3.0
        stype = 'mixed'
        
        lower_name = name.lower()
        if any(kw in lower_name for kw in ['برمجة', 'كود', 'java', 'python', 'c#', 'شيئية', 'مرئية']):
            weight = 5.0
            stype = 'programming'
        elif any(kw in lower_name for kw in ['رياضيات', 'إحصاء', 'خوارزميات', 'منطق', 'جبر']):
            weight = 5.0
            stype = 'math'
        elif any(kw in lower_name for kw in ['تصميم', 'نظم', 'إدارة', 'ثقافة', 'هندسة', 'تحليل']):
            weight = 2.5
            stype = 'theory'
            
        subjects_data.append({'name': name, 'weight': weight, 'type': stype})
    
    conn.close()
    return render_template('a.html', subjects=subjects_data)

@app.route('/refresh')
def refresh():
    rebuild_db()
    return 'database refreshed'

@app.route('/files/<path:filename>')
def files(filename):
    return send_from_directory('b', filename)

if __name__ == '__main__':
    # Download files from Drive if missing
    download_curriculum_files()
    
    # Build database on startup if it doesn't exist
    if not os.path.exists(DB_PATH):
        rebuild_db()
    app.run(debug=True)
