from flask import Flask, render_template, request, redirect, url_for, session, Response, send_file
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import csv
from io import TextIOWrapper, BytesIO
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = 'supersecretkey'
DATABASE = 'certifications.db'

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            roll_no TEXT,
            department TEXT,
            year TEXT,
            course_name TEXT,
            platform TEXT,
            domain TEXT,
            start_date TEXT,
            end_date TEXT,
            certificate_link TEXT,
            verified TEXT DEFAULT 'Yes'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT,
            department TEXT
        )
    """)

    # Admin + IT coordinator
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password_hash, role, department) VALUES (?, ?, ?, ?)",
                  ('admin', generate_password_hash('admin123'), 'admin', None))

    c.execute("SELECT * FROM users WHERE username = 'itcoordinator'")
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password_hash, role, department) VALUES (?, ?, ?, ?)",
                  ('itcoordinator', generate_password_hash('it123'), 'coordinator', 'IT'))

    users = [
        ('csecoordinator', 'cse123', 'CSE'),
        ('ececoordinator', 'ece123', 'ECE'),
        ('eeecoordinator', 'eee123', 'EEE'),
        ('cecoordinator', 'ce123', 'CE'),
        ('mecoordinator', 'me123', 'ME'),
        ('aicoordinator', 'ai123', 'AI'),
        ('aimlcoordinator', 'aiml123', 'AIML'),
        ('aidscoordinator', 'aids123', 'AIDS'),
        ('csedscoordinator', 'cseds123', 'CSE-DS'),
        ('mbacoordinator', 'mba123', 'MBA')
    ]

    for username, password, dept in users:
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if not c.fetchone():
            c.execute("INSERT INTO users (username, password_hash, role, department) VALUES (?, ?, ?, ?)",
                      (username, generate_password_hash(password), 'coordinator', dept))

    conn.commit()
    conn.close()

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    selected_year = request.form.get('year_filter') if request.method == 'POST' else ''
    selected_academic_year = request.form.get('academic_year_filter') if request.method == 'POST' else ''
    selected_course = request.form.get('course_filter') if request.method == 'POST' else ''
    selected_department = request.form.get('department_filter') if request.method == 'POST' else (session['department'] if session['role'] != 'admin' else '')


    username = session.get('username')  # or session.get('user'), as applicable

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Fetch dropdown options
    c.execute("SELECT DISTINCT year FROM certifications ORDER BY year")
    year_options = [row[0] for row in c.fetchall()]

    c.execute("SELECT DISTINCT academic_year FROM certifications ORDER BY academic_year")
    academic_year_options = [row[0] for row in c.fetchall()]

    c.execute("SELECT DISTINCT course_name FROM certifications ORDER BY course_name")
    course_options = [row[0] for row in c.fetchall()]

    c.execute("SELECT DISTINCT department FROM certifications ORDER BY department")
    department_options = [row[0] for row in c.fetchall()]



    # Build the main query
    query = "SELECT * FROM certifications"
    params = []

    if session['role'] != 'admin':
        query += " WHERE department = ?"
        params.append(session['department'])

    if selected_year:
        query += " AND" if "WHERE" in query else " WHERE"
        query += " year = ?"
        params.append(selected_year)

    if selected_academic_year:
        query += " AND" if "WHERE" in query else " WHERE"
        query += " academic_year = ?"
        params.append(selected_academic_year)

    if selected_course:
        query += " AND" if "WHERE" in query else " WHERE"
        query += " course_name = ?"
        params.append(selected_course)

    if selected_department:
        query += " AND" if "WHERE" in query else " WHERE"
        query += " department = ?"
        params.append(selected_department)


    c.execute(query, tuple(params))
    rows = c.fetchall()

    total = len(rows)
    verified = sum(1 for r in rows if r[11].lower() == 'yes')
    unverified = total - verified

    department_labels, department_counts = [], []
    course_labels, course_counts = [], []
    year_labels, year_counts = [], []
    academic_year_labels, academic_year_counts = [], []

    summary_stats = []  # default empty list for non-admins

    if session['role'] == 'admin':
        # Department-wise chart
        chart_query = "SELECT department, COUNT(*) FROM certifications"
        chart_params = []
        conditions = []

        if selected_year:
            conditions.append("year = ?")
            chart_params.append(selected_year)

        if selected_academic_year:
            conditions.append("academic_year = ?")
            chart_params.append(selected_academic_year)

        if selected_course:
            conditions.append("course_name = ?")
            chart_params.append(selected_course)

        if conditions:
            chart_query += " WHERE " + " AND ".join(conditions)

        chart_query += " GROUP BY department"
        c.execute(chart_query, tuple(chart_params))
        for dept, count in c.fetchall():
            department_labels.append(dept)
            department_counts.append(count)

        # Course-wise chart
        # c.execute("""
        #     SELECT course_name, COUNT(*) 
        #     FROM certifications 
        #     GROUP BY course_name 
        #     ORDER BY COUNT(*) DESC
        # """)
        # for course, count in c.fetchall():
        #     course_labels.append(course)
        #     course_counts.append(count)
        
        
        # Course-wise chart (with department filter if selected)
        course_query = "SELECT course_name, COUNT(*) FROM certifications"
        course_conditions = []
        course_params = []

        if selected_department:
            course_conditions.append("department = ?")
            course_params.append(selected_department)

        if selected_year:
            course_conditions.append("year = ?")
            course_params.append(selected_year)

        if selected_academic_year:
            course_conditions.append("academic_year = ?")
            course_params.append(selected_academic_year)

        if course_conditions:
            course_query += " WHERE " + " AND ".join(course_conditions)

        course_query += " GROUP BY course_name ORDER BY COUNT(*) DESC"

        c.execute(course_query, tuple(course_params))
        for course, count in c.fetchall():
            course_labels.append(course)
            course_counts.append(count)

        

        # Year-wise chart
        # year_query = "SELECT year, COUNT(*) FROM certifications"
        # year_params = []
        # year_conditions = []

        # if selected_year:
        #     year_conditions.append("year = ?")
        #     year_params.append(selected_year)

        # if selected_academic_year:
        #     year_conditions.append("academic_year = ?")
        #     year_params.append(selected_academic_year)

        # if selected_course:
        #     year_conditions.append("course_name = ?")
        #     year_params.append(selected_course)

        # if year_conditions:
        #     year_query += " WHERE " + " AND ".join(year_conditions)

        # year_query += " GROUP BY year ORDER BY year"

        # c.execute(year_query, tuple(year_params))
        # for y, count in c.fetchall():
        #     year_labels.append(y)
        #     year_counts.append(count)
        
        # Year-wise chart (including filters)
        year_query = "SELECT year, COUNT(*) FROM certifications"
        year_conditions = []
        year_params = []

        if selected_department:
            year_conditions.append("department = ?")
            year_params.append(selected_department)
        if selected_year:
            year_conditions.append("year = ?")
            year_params.append(selected_year)
        if selected_academic_year:
            year_conditions.append("academic_year = ?")
            year_params.append(selected_academic_year)
        if selected_course:
            year_conditions.append("course_name = ?")
            year_params.append(selected_course)

        if year_conditions:
            year_query += " WHERE " + " AND ".join(year_conditions)

        year_query += " GROUP BY year ORDER BY year"

        c.execute(year_query, tuple(year_params))
        for y, count in c.fetchall():
            year_labels.append(y)
            year_counts.append(count)

        

        # Academic year-wise chart
        # c.execute("""
        #     SELECT academic_year, COUNT(*) 
        #     FROM certifications 
        #     GROUP BY academic_year 
        #     ORDER BY academic_year
        # """)
        # for academic_year, count in c.fetchall():
        #     academic_year_labels.append(academic_year)
        #     academic_year_counts.append(count)

        # Academic year-wise chart(filtered)
        academic_year_query = "SELECT academic_year, COUNT(*) FROM certifications"
        academic_year_conditions = []
        academic_year_params = []

        if selected_department:
            academic_year_conditions.append("department = ?")
            academic_year_params.append(selected_department)
        if selected_year:
            academic_year_conditions.append("year = ?")
            academic_year_params.append(selected_year)
        if selected_course:
            academic_year_conditions.append("course_name = ?")
            academic_year_params.append(selected_course)

        if academic_year_conditions:
            academic_year_query += " WHERE " + " AND ".join(academic_year_conditions)

        academic_year_query += " GROUP BY academic_year ORDER BY academic_year"

        c.execute(academic_year_query, tuple(academic_year_params))
        for academic_year, count in c.fetchall():
            academic_year_labels.append(academic_year)
            academic_year_counts.append(count)

        # Summary table data (filtered)
        summary_query = "SELECT department, course_name, COUNT(*) FROM certifications"
        summary_conditions = []
        summary_params = []

        if selected_department:
            summary_conditions.append("department = ?")
            summary_params.append(selected_department)
        if selected_year:
            summary_conditions.append("year = ?")
            summary_params.append(selected_year)
        if selected_academic_year:
            summary_conditions.append("academic_year = ?")
            summary_params.append(selected_academic_year)
        if selected_course:
            summary_conditions.append("course_name = ?")
            summary_params.append(selected_course)

        if summary_conditions:
            summary_query += " WHERE " + " AND ".join(summary_conditions)

        summary_query += " GROUP BY department, course_name ORDER BY department, course_name"

        c.execute(summary_query, tuple(summary_params))
        summary_stats = c.fetchall()

        
        
    conn.close()

    return render_template("index.html",
        username=username,
        certifications=rows,
        years=year_options,
        selected_year=selected_year,
        academic_years=academic_year_options,
        selected_academic_year=selected_academic_year,
        courses=course_options,
        selected_course=selected_course,
        total=total,
        verified=verified,
        unverified=unverified,
        role=session['role'],
        department_labels=department_labels,
        department_counts=department_counts,
        course_labels=course_labels,
        course_counts=course_counts,
        year_labels=year_labels,
        year_counts=year_counts,
        academic_year_labels=academic_year_labels,
        academic_year_counts=academic_year_counts,
        departments=department_options,
        selected_department=selected_department,
        summary_stats=summary_stats
    )



@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = (
            request.form['name'],
            request.form['roll_no'],
            session['department'],
            request.form['year'],
            request.form['course_name'],
            request.form['platform'],
            request.form['domain'],
            request.form['start_date'],
            request.form['end_date'],
            request.form['certificate_link'],
            request.form['academic_year']
        )

        # Using 'with' statement to ensure connection is closed automatically
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO certifications 
                (name, roll_no, department, year, course_name, platform, domain, start_date, end_date, certificate_link, academic_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
            conn.commit()

        return redirect(url_for('index'))

    return render_template("submit.html")


@app.route('/edit/<int:cert_id>', methods=['GET', 'POST'])
def edit_cert(cert_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM certifications WHERE id = ?", (cert_id,))
    cert = c.fetchone()

    if session['role'] != 'admin' and cert[3] != session['department']:
        conn.close()
        return "Unauthorized", 403

    if request.method == 'POST':
        updated = (
            request.form['name'],
            request.form['roll_no'],
			request.form['department'],
            request.form['year'],
            request.form['course_name'],
            request.form['platform'],
            request.form['domain'],
            request.form['start_date'],
            request.form['end_date'],
            request.form['certificate_link'],
            request.form['verified'],
            cert_id
        )
        c.execute("""
            UPDATE certifications SET
                name = ?, roll_no = ?, department = ?, year = ?, course_name = ?, platform = ?,
                domain = ?, start_date = ?, end_date = ?, certificate_link = ?, verified = ?
            WHERE id = ?
        """, updated)
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    conn.close()
    return render_template("edit.html", cert=cert)

@app.route('/delete/<int:cert_id>', methods=['POST'])
def delete_cert(cert_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT department FROM certifications WHERE id = ?", (cert_id,))
    row = c.fetchone()

    if not row:
        return "Certification not found", 404

    if session['role'] != 'admin' and row[0] != session['department']:
        conn.close()
        return "Unauthorized", 403

    c.execute("DELETE FROM certifications WHERE id = ?", (cert_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/import', methods=['GET', 'POST'])
def import_csv():
    if 'username' not in session:
        return redirect(url_for('login'))

    message = None
    if request.method == 'POST':
        file = request.files['file']
        if not file or not file.filename.endswith('.csv'):
            message = "Please upload a valid CSV file."
        else:
            try:
                stream = TextIOWrapper(file.stream)
                reader = csv.DictReader(stream)
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                for row in reader:
                    c.execute("""
                        INSERT INTO certifications (
                            name, roll_no, department, year, course_name,
                            platform, domain, start_date, end_date, certificate_link, verified, academic_year
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['name'],
                        row['roll_no'],
                        session['department'],
                        row['year'],
                        row['course_name'],
                        row['platform'],
                        row['domain'],
                        row['start_date'],
                        row['end_date'],
                        row['certificate_link'],
						row['verified'],
                        row['academic_year']
                    ))
                conn.commit()
                conn.close()
                message = "CSV imported successfully!"
            except Exception as e:
                message = f"Error: {str(e)}"

    return render_template('import.html', message=message)

@app.route('/export')
def export_csv():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    if session['role'] == 'admin':
        c.execute("SELECT * FROM certifications")
    else:
        c.execute("SELECT * FROM certifications WHERE department = ?", (session['department'],))
    rows = c.fetchall()
    conn.close()

    headers = ['id', 'name', 'roll_no', 'department', 'year', 'course_name', 'platform', 'domain', 'start_date', 'end_date', 'certificate_link', 'verified']
    csv_data = ",".join(headers) + "\n"
    for row in rows:
        csv_data += ",".join(str(cell) for cell in row) + "\n"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=certifications.csv"}
    )

@app.route('/export_excel')
def export_excel():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    if session['role'] == 'admin':
        c.execute("SELECT * FROM certifications")
    else:
        c.execute("SELECT * FROM certifications WHERE department = ?", (session['department'],))
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Certifications"

    headers = ['ID', 'Name', 'Roll No', 'Department', 'Year', 'Course Name',
               'Platform', 'Domain', 'Start Date', 'End Date', 'Certificate Link', 'Verified']
    ws.append(headers)

    for row in rows:
        ws.append(list(row))

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    return send_file(
        output,
        download_name="certifications.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['username'] = user[1]
            session['role'] = user[3]
            session['department'] = user[4]
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)
