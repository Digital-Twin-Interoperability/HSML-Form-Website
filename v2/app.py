import os
import json
import tempfile
import datetime
import subprocess

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, send_file
)
import mysql.connector

# Import functions from the provided API modules.
# These functions are defined in Registration_API_v6.py and CLItool.py.
from Registration_API_v6 import extract_did_from_private_key, generate_did_key

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a strong secret key!

# Database configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "rootbeer",
    "database": "did_registry",
    "auth_plugin": "mysql_native_password"
}

# Directories for temporary PEM file storage and generated output files.
TEMP_DIR = os.path.join(os.getcwd(), 'temp_keys')
GENERATED_DIR = os.path.join(os.getcwd(), 'generated_files')
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)

# HSML context URL (same for all HSML JSON files)
HSML_CONTEXT = "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld"

####################
# Helper Functions #
####################

def get_db_connection():
    """Return a new database connection using the config."""
    return mysql.connector.connect(**db_config)

def init_db():
    """Initialize the database tables if they do not exist."""
    db = get_db_connection()
    cursor = db.cursor()
    # Table for registered users (Person or Organization)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        did VARCHAR(255) UNIQUE,
        name VARCHAR(255),
        type ENUM('Person','Organization'),
        public_key TEXT,
        metadata JSON
    )
    """)
    # Table for other HSML objects (Agent, Entity, Credential, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hsml_objects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        did VARCHAR(255) UNIQUE,
        type VARCHAR(50),
        name VARCHAR(255),
        metadata JSON,
        registered_by VARCHAR(255)
    )
    """)
    db.commit()
    cursor.close()
    db.close()

# Initialize database before handling any requests.
# @app.before_first_request
def initialize():
    init_db()

def save_generated_file(content, filename):
    """Save a string to a file in the GENERATED_DIR and return the file path."""
    filepath = os.path.join(GENERATED_DIR, filename)
    with open(filepath, 'w') as f:
        f.write(content)
    return filepath

####################
# Routes           #
####################

@app.route('/')
def home():
    # Home page with two buttons: Login and New User.
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Ensure a file was uploaded.
        if 'pem_file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        pem_file = request.files['pem_file']
        if pem_file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        # Save the uploaded PEM file temporarily.
        temp_path = os.path.join(TEMP_DIR, pem_file.filename)
        pem_file.save(temp_path)
        
        try:
            # Extract the DID from the uploaded PEM file.
            user_did = extract_did_from_private_key(temp_path)
        except Exception as e:
            flash('Error processing PEM file: ' + str(e))
            os.remove(temp_path)
            return redirect(request.url)
        
        os.remove(temp_path)  # Clean up the temporary file.
        
        # Check if this DID exists in the users table.
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE did = %s", (user_did,))
        user = cursor.fetchone()
        cursor.close()
        db.close()
        
        if user:
            # If user is found, set session data and redirect to the dashboard.
            session['user_did'] = user['did']
            session['user_name'] = user['name']
            session['user_type'] = user['type']
            # flash('Login successful. Welcome, ' + user['name'] + '!')
            return redirect(url_for('dashboard'))
        else:
            flash('DID not found. Please register as a new user.')
            return redirect(url_for('new_user'))
    return render_template('login.html')

@app.route('/new_user', methods=['GET'])
def new_user():
    # Display a page where the user can choose to register as Person or Organization.
    return render_template('new_user.html')

@app.route('/register/person', methods=['GET', 'POST'])
def register_person():
    if request.method == 'POST':
        name = request.form.get('name')
        birthdate = request.form.get('birthdate')
        email = request.form.get('email')
        
        if not name or not birthdate or not email:
            flash('Please fill in all required fields.')
            return redirect(request.url)
        
        # Generate a new DID and private key.
        try:
            did_key, private_key_pem = generate_did_key()
        except Exception as e:
            flash('Error generating DID: ' + str(e))
            return redirect(request.url)
        
        # Build the HSML JSON for a Person.
        person_json = {
            "@context": HSML_CONTEXT,
            "@type": "Person",
            "name": name,
            "birthDate": birthdate,
            "email": email,
            "swid": did_key
        }
        # Remove any fields that are empty.
        person_json = {k: v for k, v in person_json.items() if v}
        person_json_str = json.dumps(person_json, indent=4)
        
        # Save the JSON and PEM files on the server.
        json_filename = f"{name.replace(' ', '_')}_Person.json"
        pem_filename = f"{name.replace(' ', '_')}_private_key.pem"
        save_generated_file(person_json_str, json_filename)
        save_generated_file(private_key_pem, pem_filename)
        
        # Insert the new user into the database.
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (did, name, type, public_key, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, (did_key, name, 'Person', did_key.replace("did:key:", ""), json.dumps(person_json)))
        db.commit()
        cursor.close()
        db.close()
        
        # Set session data.
        session['user_did'] = did_key
        session['user_name'] = name
        session['user_type'] = 'Person'
        
        flash('Registration successful!')
        return render_template('results.html', hsml_json=person_json_str,
                               json_filename=json_filename, pem_filename=pem_filename)
    
    return render_template('person.html')

@app.route('/register/organization', methods=['GET', 'POST'])
def register_organization():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        url_field = request.form.get('url')
        address = request.form.get('address')
        founding_date = request.form.get('founding_date')
        email = request.form.get('email')
        
        if not name or not description or not url_field or not address or not founding_date or not email:
            flash('Please fill in all required fields.')
            return redirect(request.url)
        
        try:
            did_key, private_key_pem = generate_did_key()
        except Exception as e:
            flash('Error generating DID: ' + str(e))
            return redirect(request.url)
        
        # Build the HSML JSON for an Organization.
        org_json = {
            "@context": HSML_CONTEXT,
            "@type": "Organization",
            "name": name,
            "description": description,
            "url": url_field,
            "address": address,
            "foundingDate": founding_date,
            "email": email,
            "swid": did_key
        }
        org_json = {k: v for k, v in org_json.items() if v}
        org_json_str = json.dumps(org_json, indent=4)
        
        json_filename = f"{name.replace(' ', '_')}_Organization.json"
        pem_filename = f"{name.replace(' ', '_')}_private_key.pem"
        save_generated_file(org_json_str, json_filename)
        save_generated_file(private_key_pem, pem_filename)
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO users (did, name, type, public_key, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, (did_key, name, 'Organization', did_key.replace("did:key:", ""), json.dumps(org_json)))
        db.commit()
        cursor.close()
        db.close()
        
        session['user_did'] = did_key
        session['user_name'] = name
        session['user_type'] = 'Organization'
        
        flash('Organization registration successful!')
        return render_template('results.html', hsml_json=org_json_str,
                               json_filename=json_filename, pem_filename=pem_filename)
    
    return render_template('organization.html')

@app.route('/dashboard')
def dashboard():
    if 'user_did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    # Dashboard page with buttons for creating Agent, Entity, and Credential.
    return render_template('existing_user_dashboard.html', user_name=session.get('user_name'))

@app.route('/create/agent', methods=['GET', 'POST'])
def create_agent():
    if 'user_did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        creator = session.get('user_name')  # Current user becomes the creator.
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if not name or not description:
            flash('Please provide all required fields.')
            return redirect(request.url)
        
        try:
            obj_did, _ = generate_did_key()  # Generate a new DID for the Agent.
        except Exception as e:
            flash('Error generating DID: ' + str(e))
            return redirect(request.url)
        
        agent_json = {
            "@context": HSML_CONTEXT,
            "@type": "Agent",
            "name": name,
            "swid": obj_did,
            "creator": {"@type": "Person", "name": creator},
            "dateCreated": current_date,
            "dateModified": current_date,
            "description": description
        }
        agent_json = {k: v for k, v in agent_json.items() if v}
        agent_json_str = json.dumps(agent_json, indent=4)
        
        json_filename = f"{name.replace(' ', '_')}_Agent.json"
        save_generated_file(agent_json_str, json_filename)
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO hsml_objects (did, type, name, metadata, registered_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (obj_did, "Agent", name, json.dumps(agent_json), session.get('user_did')))
        db.commit()
        cursor.close()
        db.close()
        
        flash('Agent created successfully!')
        return render_template('results.html', hsml_json=agent_json_str, json_filename=json_filename)
    
    return render_template('agent.html')

@app.route('/create/entity', methods=['GET', 'POST'])
def create_entity():
    if 'user_did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        if not name or not description:
            flash('Please provide all required fields.')
            return redirect(request.url)
        
        try:
            obj_did, _ = generate_did_key()
        except Exception as e:
            flash('Error generating DID: ' + str(e))
            return redirect(request.url)
        
        entity_json = {
            "@context": HSML_CONTEXT,
            "@type": "Entity",
            "name": name,
            "description": description,
            "swid": obj_did
        }
        entity_json = {k: v for k, v in entity_json.items() if v}
        entity_json_str = json.dumps(entity_json, indent=4)
        
        json_filename = f"{name.replace(' ', '_')}_Entity.json"
        save_generated_file(entity_json_str, json_filename)
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO hsml_objects (did, type, name, metadata, registered_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (obj_did, "Entity", name, json.dumps(entity_json), session.get('user_did')))
        db.commit()
        cursor.close()
        db.close()
        
        flash('Entity created successfully!')
        return render_template('results.html', hsml_json=entity_json_str, json_filename=json_filename)
    
    return render_template('entity.html')

@app.route('/create/credential', methods=['GET', 'POST'])
def create_credential():
    if 'user_did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        issued_by = session.get('user_name')
        access_authorization = request.form.get('access_authorization')
        authorized_for_domain = request.form.get('authorized_for_domain')
        
        if not name or not description or not access_authorization or not authorized_for_domain:
            flash('Please provide all required fields.')
            return redirect(request.url)
        
        try:
            obj_did, _ = generate_did_key()
        except Exception as e:
            flash('Error generating DID: ' + str(e))
            return redirect(request.url)
        
        credential_json = {
            "@context": HSML_CONTEXT,
            "@type": "Credential",
            "name": name,
            "swid": obj_did,
            "description": description,
            "issuedBy": {"@type": "Person", "name": issued_by},
            "accessAuthorization": {"@type": "Agent", "name": access_authorization},
            "authorizedForDomain": {"@type": "Agent", "name": authorized_for_domain}
        }
        credential_json = {k: v for k, v in credential_json.items() if v}
        credential_json_str = json.dumps(credential_json, indent=4)
        
        json_filename = f"{name.replace(' ', '_')}_Credential.json"
        save_generated_file(credential_json_str, json_filename)
        
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO hsml_objects (did, type, name, metadata, registered_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (obj_did, "Credential", name, json.dumps(credential_json), session.get('user_did')))
        db.commit()
        cursor.close()
        db.close()
        
        flash('Credential created successfully!')
        return render_template('results.html', hsml_json=credential_json_str, json_filename=json_filename)
    
    return render_template('credential.html')

@app.route('/download/<filename>')
def download_file(filename):
    # Serve generated JSON or PEM files for download.
    return send_from_directory(GENERATED_DIR, filename, as_attachment=True)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        init_db()  # Initialize the database before running the app
    app.run(debug=True)
