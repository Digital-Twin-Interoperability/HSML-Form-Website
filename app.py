from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import os
import json
import requests

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key")

# Set the API base URL (adjust if your FastAPI API is hosted remotely)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

@app.route('/')
def landing():
    return render_template('landing.html')

# Login: upload a .pem file to the FastAPI /entity/login endpoint for DID extraction and authentication.
@app.route('/entity/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if 'pem_file' not in request.files:
            error = "No file part in request."
            return render_template('login.html', error=error)
        file = request.files['pem_file']
        if file.filename == '':
            error = "No file selected."
            return render_template('login.html', error=error)
        try:
            # Forward the uploaded file directly to the FastAPI endpoint.
            files = {'pem_file': (file.filename, file.stream, file.content_type)}
            response = requests.post(f"{API_BASE_URL}/entity/login", files=files)
            if response.status_code != 200:
                error = f"Login failed: {response.json().get('detail', 'Unknown error')}"
                return render_template('login.html', error=error)
            data = response.json()
            flash(f"Login successful. Your DID: {data.get('did')}")
            session["did"] = data.get("did")
            return redirect(url_for('create_hsml'))
        except Exception as e:
            error = f"Error during login: {str(e)}"
    return render_template('login.html', error=error)

# Registration: collect the HSML data from the form and send it to the FastAPI /entity/register-user endpoint.
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hsml_type = request.form.get('hsml_type')
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": hsml_type
        }
        if hsml_type == "Person":
            hsml_obj["name"] = request.form.get('name').strip()
            hsml_obj["birthDate"] = request.form.get('birth_date').strip()
            hsml_obj["email"] = request.form.get('email').strip()
        elif hsml_type == "Organization":
            hsml_obj["name"] = request.form.get('org_name').strip()
            hsml_obj["description"] = request.form.get('description').strip()
        else:
            flash("Invalid HSML type selected for registration.")
            return redirect(url_for('register'))
        
        try:
            response = requests.post(f"{API_BASE_URL}/entity/register-user", json=hsml_obj, timeout=15)
        except Exception as e:
            flash(f"Registration service unreachable: {e}")
            return redirect(url_for('register'))
        
        if response.status_code == 200:
            data = response.json()
            did = data.get("did")
            private_key = data.get("private_key")
            hsml_json_str = json.dumps(data.get("hsml", hsml_obj), indent=2)
            return render_template("result.html", json_str=hsml_json_str, private_key=private_key, did=did)
        else:
            try:
                error_msg = response.json().get('detail', '')
            except ValueError:
                error_msg = response.text
            flash(f"Registration failed: {error_msg}")
            return redirect(url_for('register'))
    return render_template('register.html')

# HSML creation form available after login. This page allows logged-in users to create new entities.
@app.route('/create', methods=['GET', 'POST'])
def create_hsml():
    if request.method == 'POST':
        hsml_type = request.form.get("hsml_type")
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": hsml_type
        }
        if hsml_type == "Person":
            hsml_obj["name"] = request.form.get("name")
            hsml_obj["birthDate"] = request.form.get("birth_date")
            hsml_obj["email"] = request.form.get("email")
        elif hsml_type == "Entity":
            hsml_obj["name"] = request.form.get("entity_name")
            hsml_obj["description"] = request.form.get("description")
        else:
            hsml_obj["name"] = request.form.get("name") or request.form.get("entity_name")
            hsml_obj["description"] = request.form.get("description", "")
        
        # Retrieve the logged-in user's DID from the session.
        registered_by = session.get("did")
        payload = {"entity": hsml_obj, "registered_by": registered_by}
        try:
            api_response = requests.post(f"{API_BASE_URL}/register_entity", json=payload, timeout=15)
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(url_for('create_hsml'))
        if api_response.status_code == 200:
            data = api_response.json()
            hsml_json_str = json.dumps(data, indent=2)
            return render_template("result.html", json_str=hsml_json_str, private_key=data.get("private_key", ""), did=data.get("did", ""))
        else:
            try:
                err_msg = api_response.json().get('detail', '')
            except ValueError:
                err_msg = api_response.text
            flash(f"Entity registration failed: {err_msg}")
            return redirect(url_for('create_hsml'))
    return render_template('index.html')

# Endpoint to serve the private key file for download if desired.
@app.route('/download_key')
def download_key():
    private_key = request.args.get('key')
    if not private_key:
        return "No key provided", 400
    response = make_response(private_key)
    response.headers["Content-Disposition"] = "attachment; filename=mykey.pem"
    response.headers["Content-Type"] = "application/octet
