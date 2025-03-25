<<<<<<< Updated upstream
from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests, json, os
=======
import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, make_response
>>>>>>> Stashed changes

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key")

<<<<<<< Updated upstream
# URL of the FastAPI registration service (set via environment or default)
FASTAPI_URL = os.getenv("REGISTRATION_API_URL", "http://localhost:8000")

# Landing page
=======
# Set the API base URL (adjust if your FastAPI API is hosted remotely)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Landing page offering login or registration
>>>>>>> Stashed changes
@app.route('/')
def landing():
    return render_template('landing.html')

<<<<<<< Updated upstream
# Login: show form and process .pem file upload
@app.route('/login', methods=['GET', 'POST'])
=======
# Login: upload a .pem file to the new API for DID extraction and authentication.
@app.route('/entity/login', methods=['GET', 'POST'])
>>>>>>> Stashed changes
def login():
    error = None
    if request.method == 'POST':
        if 'pem_file' not in request.files:
            error = "No file part in request."
            return render_template('login.html', error=error)
        pem_file = request.files['pem_file']
        if pem_file.filename == '':
            error = "No file selected."
            return render_template('login.html', error=error)
<<<<<<< Updated upstream
        try:
            files = {'pem_file': (pem_file.filename, pem_file.stream, pem_file.mimetype)}
            response = requests.post(f"{FASTAPI_URL}/login", files=files, timeout=10)
        except Exception as e:
            error = f"Could not reach authentication service: {e}"
            return render_template('login.html', error=error)
        if response.status_code == 200:
            data = response.json()
            user_did = data.get("did")
            # Store the DID in the session
            session["did"] = user_did
            flash(f"Login successful. Your DID: {user_did}")
            return redirect(url_for('create_hsml'))
        else:
            try:
                err_detail = response.json().get('detail', '')
            except ValueError:
                err_detail = response.text
            error = f"Login failed: {err_detail}"
            return render_template('login.html', error=error)
    return render_template('login.html', error=error)

# User Registration: register a new user (Person or Organization)
=======
        if file:
            try:
                # Forward the uploaded file directly to the FastAPI /login endpoint.
                files = {'pem_file': (file.filename, file.stream, file.content_type)}
                response = requests.post(f"{API_BASE_URL}/entity/login", files=files)
                if response.status_code != 200:
                    # The API returns error details in a JSON "detail" field.
                    error = f"Login failed: {response.json().get('detail', 'Unknown error')}"
                    return render_template('login.html', error=error)
                data = response.json()
                flash(f"Login successful. Your DID: {data.get('did')}")
                # Here you could also store the DID or other auth details in session if needed.
                return redirect(url_for('create_hsml'))
            except Exception as e:
                error = f"Error during login: {str(e)}"
    return render_template('login.html', error=error)

# Registration: collect the HSML data from the form and send it to the new API.
>>>>>>> Stashed changes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hsml_type = request.form.get('hsml_type')
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": hsml_type
        }
<<<<<<< Updated upstream
        try:
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
        except AttributeError:
            flash("Please fill out all required fields.")
            return redirect(url_for('register'))
        
        try:
            response = requests.post(f"{FASTAPI_URL}/register", json=hsml_obj, timeout=15)
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

# Create HSML entity: a page where logged-in users create new entities.
# For simplicity, we assume this form submits to /register_entity.
@app.route('/create', methods=['GET', 'POST'])
=======
        if hsml_type == "Person":
            hsml_obj["name"] = request.form.get('name')
            hsml_obj["birthDate"] = request.form.get('birth_date')
            hsml_obj["email"] = request.form.get('email')
        elif hsml_type == "Organization":
            hsml_obj["name"] = request.form.get('org_name')
            hsml_obj["description"] = request.form.get('description')
        # Call the FastAPI /register-user endpoint with the HSML JSON.
        try:
            response = requests.post(f"{API_BASE_URL}/entity/register-user", json=hsml_obj)
            if response.status_code != 200:
                flash(f"Registration failed: {response.json().get('detail', 'Unknown error')}")
                return redirect(url_for('register'))
            result = response.json()
            did = result.get("did")
            private_key = result.get("private_key")
            hsml_data = result.get("hsml")
            hsml_json_str = json.dumps(hsml_data, indent=2)
            # Render a result page displaying the registered HSML JSON and private key.
            return render_template("result.html", json_str=hsml_json_str, private_key=private_key)
        except Exception as e:
            flash(f"Error during registration: {str(e)}")
            return redirect(url_for('register'))
    return render_template('register.html')

# HSML creation form available after login.
@app.route('/create')
>>>>>>> Stashed changes
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
        
        # Retrieve the logged-in user's DID from the session
        registered_by = session.get("did")
        # Include registered_by in the payload
        payload = {"entity": hsml_obj, "registered_by": registered_by}
        try:
            api_response = requests.post(f"{FASTAPI_URL}/register_entity", json=payload, timeout=15)
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

<<<<<<< Updated upstream
# Endpoint to handle new entity registration via POST (if you want to separate it)
@app.route('/register_entity', methods=['POST'])
def register_entity_form():
    # This endpoint is similar to the POST block in /create.
    # For simplicity, we use the same logic here.
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
    payload = {"entity": hsml_obj}
    try:
        api_response = requests.post(f"{FASTAPI_URL}/register_entity", json=payload, timeout=15)
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
=======
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
>>>>>>> Stashed changes

if __name__ == '__main__':
    app.run(debug=True)
