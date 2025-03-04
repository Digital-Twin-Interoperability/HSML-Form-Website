from flask import Flask, render_template, request, redirect, url_for, flash, make_response
import json, os
from CLItool import extract_did_from_private_key
from Registration_API_v6 import generate_did_key  # Do not change Registration_API_v6.py

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Set your secret key for session management

# Landing page offering login or register
@app.route('/')
def landing():
    return render_template('landing.html')

# Login: upload a .pem file, decode using CLItool.py
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if 'pem_file' not in request.files:
            error = "No file part"
            return render_template('login.html', error=error)
        file = request.files['pem_file']
        if file.filename == '':
            error = "No selected file"
            return render_template('login.html', error=error)
        if file:
            # Save the uploaded file temporarily
            temp_dir = "temp"
            os.makedirs(temp_dir, exist_ok=True)
            filepath = os.path.join(temp_dir, file.filename)
            file.save(filepath)
            try:
                user_did = extract_did_from_private_key(filepath)
                # Here you would normally check the DID against your DB.
                flash(f"Login successful. Your DID: {user_did}")
                return redirect(url_for('create_hsml'))
            except Exception as e:
                error = f"Error processing .pem file: {str(e)}"
            finally:
                os.remove(filepath)
    return render_template('login.html', error=error)

# Registration: show a modified HSML creation form (only Person or Organization)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hsml_type = request.form.get('hsml_type')
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": hsml_type
        }
        if hsml_type == "Person":
            hsml_obj["name"] = request.form.get('name')
            hsml_obj["birthDate"] = request.form.get('birth_date')
            hsml_obj["email"] = request.form.get('email')
        elif hsml_type == "Organization":
            hsml_obj["name"] = request.form.get('org_name')
            hsml_obj["description"] = request.form.get('description')
        # Generate DID:key and private key using the CLI tool via Registration_API_v6.py
        try:
            did_key, private_key = generate_did_key()
        except Exception as e:
            flash(f"Error generating DID key: {str(e)}")
            return redirect(url_for('register'))
        hsml_obj["swid"] = did_key  # Attach the generated DID to the HSML JSON
        hsml_json_str = json.dumps(hsml_obj, indent=2)
        # Render the result page with the HSML JSON and pass along the private key content
        return render_template("result.html", json_str=hsml_json_str, private_key=private_key)
    return render_template('register.html')

# HSML creation form (full functionality) available after login
@app.route('/create')
def create_hsml():
    return render_template('index.html')

# Endpoint to serve the private key file for download (if desired)
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
