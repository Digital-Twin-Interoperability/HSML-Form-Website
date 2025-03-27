from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import os
import json
import requests
import datetime

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
            # Redirect to selection page after a successful login.
            return redirect(url_for('selection'))
        except Exception as e:
            error = f"Error during login: {str(e)}"
    return render_template('login.html', error=error)

# Selection page route: Presents three buttons for Entity, Agent, and Credential.
@app.route('/selection')
def selection():
    if 'did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    return render_template('selection.html')

# Registration: collect HSML data from the form and send it to the FastAPI /entity/register-user endpoint.
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

# Entity Creation Route
@app.route('/create', methods=['GET', 'POST'])
def create_entity():
    # Ensure the user is logged in
    if 'did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Entity",
            "name": request.form.get("entity_name"),
            "description": request.form.get("description")
        }
        
        registered_by = session.get("did")
        payload = {"entity": hsml_obj, "registered_by": registered_by}
        try:
            # Post to the API endpoint for registering an entity.
            api_response = requests.post(f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15)
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(url_for('create_entity'))
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
            return redirect(url_for('create_entity'))
    return render_template('entity.html')

# Agent Creation Route
@app.route('/create/agent', methods=['GET', 'POST'])
def create_agent():
    if 'did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('agent_name')
        description = request.form.get('agent_description')
        
        # Debug prints for agent fields.
        print("DEBUG: agent_name =", name)
        print("DEBUG: agent_description =", description)
        
        if not name or not description:
            flash('Please provide all required fields.')
            return redirect(request.url)
        
        creator = session.get('user_name')  # Optional: use session value for creator's name.
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        
        agent_json = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Agent",
            "name": name,
            "creator": creator if creator else "Unknown",
            "dateCreated": current_date,
            "dateModified": current_date,
            "description": description
        }
        
        payload = {
            "entity": agent_json,
            "registered_by": session.get("did")
        }
        
        # Debug print the payload for Agent creation.
        print("DEBUG: Agent Payload:")
        print(json.dumps(payload, indent=2))
        
        try:
            response = requests.post(f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15)
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(request.url)
        
        if response.status_code == 200:
            data = response.json()
            hsml_json_str = json.dumps(data.get("metadata", agent_json), indent=2)
            private_key = data.get("private_key", "")
            flash("Agent created successfully!")
            return render_template('result.html', json_str=hsml_json_str, private_key=private_key, did=data.get("did"))
        else:
            try:
                err_msg = response.json().get('detail', 'Unknown error')
            except Exception:
                err_msg = response.text
            flash(f"Agent registration failed: {err_msg}")
            return redirect(request.url)
    
    return render_template('agent.html')

# Credential Creation Route
@app.route('/create/credential', methods=['GET', 'POST'])
def create_credential():
    if 'did' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('credential_name')
        description = request.form.get('credential_description')
        access_authorization = request.form.get('access_authorization')
        authorized_for_domain = request.form.get('authorized_for_domain')
        
        if not name or not description or not access_authorization or not authorized_for_domain:
            flash('Please provide all required fields.')
            return redirect(request.url)
        
        # Check for the uploaded .pem file.
        if 'domain_pem' not in request.files:
            flash('Please upload the private key file for the Agent.')
            return redirect(request.url)
        
        domain_pem_file = request.files['domain_pem']
        if domain_pem_file.filename == '':
            flash('No file selected for the domain PEM key.')
            return redirect(request.url)
        
        try:
            # Read the uploaded file content as text.
            domain_pem_content = domain_pem_file.read().decode('utf-8')
        except Exception as e:
            flash(f"Error reading domain PEM file: {e}")
            return redirect(request.url)
        
        credential_json = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Credential",
            "name": name,
            "description": description,
            "issuedBy": {"swid": session.get("did")},
            "accessAuthorization": {"swid": access_authorization},
            "authorizedForDomain": {"swid": authorized_for_domain, "name": authorized_for_domain}
        }
        
        payload = {
            "entity": credential_json,
            "registered_by": session.get("did"),
            "domain_pem": domain_pem_content
        }
        
        # Debug print the payload for Credential creation.
        print("DEBUG: Credential Payload:")
        print(json.dumps(payload, indent=2))
        
        try:
            response = requests.post(f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15)
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(request.url)
        
        if response.status_code == 200:
            data = response.json()
            hsml_json_str = json.dumps(data.get("metadata", credential_json), indent=2)
            private_key = data.get("private_key", "")
            flash("Credential created successfully!")
            return render_template('result.html', json_str=hsml_json_str, private_key=private_key, did=data.get("did"))
        else:
            try:
                err_msg = response.json().get('detail', 'Unknown error')
            except Exception:
                err_msg = response.text
            flash(f"Credential registration failed: {err_msg}")
            return redirect(request.url)
    
    return render_template('credential.html')

# Endpoint to serve the private key file for download if desired.
@app.route('/download_key')
def download_key():
    private_key = request.args.get('key')
    if not private_key:
        return "No key provided", 400
    response = make_response(private_key)
    response.headers["Content-Disposition"] = "attachment; filename=mykey.pem"
    response.headers["Content-Type"] = "application/octet-stream"
    return response

if __name__ == '__main__':
    app.run(debug=True)
