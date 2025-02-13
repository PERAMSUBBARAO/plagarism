from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from werkzeug.utils import secure_filename
import os

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "supersecretkey"

# Directories for file uploads
app.config['UPLOAD_FOLDER'] = './uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database connection helper (MySQL)
def query_db(query, args=(), one=False):
    conn = mysql.connector.connect(
        host="localhost",  # MySQL host
        user="root",       # MySQL username
        password="",       # MySQL password
        database="plagiarism"  # Your MySQL database name
    )
    cursor = conn.cursor()
    cursor.execute(query, args)
    rv = cursor.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# Route for homepage
@app.route('/')
def home():
    return render_template('home.html')

# Route for signup
@app.route('/signup', methods=['POST'])
def signup():
    username = request.form['username']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])
    try:
        query_db('INSERT INTO Users (Username, Email, Password) VALUES (%s, %s, %s)', (username, email, password))
        flash('Signup successful! Please login.')
        return redirect(url_for('home'))
    except mysql.connector.IntegrityError:
        flash('Username or Email already exists.')
        return redirect(url_for('home'))

# Route for login
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user = query_db('SELECT * FROM Users WHERE Username = %s', (username,), one=True)
    if user and check_password_hash(user[3], password):  # Assuming password is in the 4th column
        session['user_id'] = user[0]
        session['username'] = user[1]
        return redirect(url_for('checker'))
    flash('Invalid username or password.')
    return redirect(url_for('home'))

# Route for checker (plagiarism checking)
@app.route('/checker', methods=['GET', 'POST'])
def checker():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        file = request.files['file']
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                content = filename

            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="",
                database="plagiarism"
            )
            cursor = conn.cursor()

            try:
                # Insert into documents table
                insert_doc_query = """
                INSERT INTO documents 
                (UserID, DocumentName, Content, UploadDate) 
                VALUES (%s, %s, %s, NOW())
                """
                cursor.execute(insert_doc_query, (
                    session['user_id'], 
                    filename, 
                    content[:5000]
                ))
                
                # Get the last inserted document ID
                document_id = cursor.lastrowid

                # Simulate plagiarism analysis
                plagiarism_score, matched_sources = simulate_plagiarism_analysis(file_path)

                # Insert into plagiarismresults table
                insert_result_query = """
                INSERT INTO plagarismresults 
                (DocumentID, PlagiarismScore, MatchedSources, AnalysisDate) 
                VALUES (%s, %s, %s, NOW())
                """
                cursor.execute(insert_result_query, (
                    document_id, 
                    plagiarism_score, 
                    ', '.join(matched_sources)
                ))

                # Commit the transaction
                conn.commit()

                print("Inserted document:", insert_doc_query, session['user_id'], filename, content[:5000])
                print("Inserted plagiarism result:", insert_result_query, document_id, plagiarism_score, ', '.join(matched_sources))

                return jsonify({
                    'status': 'success',
                    'plagiarism_score': plagiarism_score,
                    'matched_sources': matched_sources,
                    'document_id': document_id
                })

            except mysql.connector.Error as err:
                print(f"Database error: {err}")
                flash(f"Database error: {err}")
                conn.rollback()
                return jsonify({
                    'status': 'error',
                    'message': str(err)
                }), 500

            finally:
                cursor.close()
                conn.close()

    return render_template('plagiarism.html')


# Simulate the plagiarism analysis
def simulate_plagiarism_analysis(file_path):
    # For the sake of this example, return a dummy plagiarism score and matched sources
    plagiarism_score = 28  # Example score
    matched_sources = [
        "scholar.google.com Academic publications and research papers",
        "research-hub.org Web-based research and reference articles",
        "industry-insights.com Industry-specific publications",
        "learning-platform.edu Educational websites and resources"
    ]
    return plagiarism_score, matched_sources

# Route for logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
