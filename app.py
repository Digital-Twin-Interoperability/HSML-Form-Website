from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
)
import os
import json
import requests
import tempfile
import datetime
import uuid

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_secret_key")

# Set the API base URL (adjust if your FastAPI API is hosted remotely)
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


@app.route("/")
def landing():
    return render_template("landing.html")


# Login: Upload a .pem file to /entity/login for authentication.
@app.route("/entity/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        print("DEBUG: Login route triggered.")  # Debug statement

        # Check if the file part is in the request
        if "pem_file" not in request.files:
            error = "No file part in request."
            print("DEBUG: No file part in request.")  # Debug statement
            return render_template("login.html", error=error)

        file = request.files["pem_file"]
        if file.filename == "":
            error = "No file selected."
            print("DEBUG: No file selected.")  # Debug statement
            return render_template("login.html", error=error)

        try:
            # Send the file directly to the FastAPI endpoint
            files = {"pem_file": (file.filename, file.stream, file.content_type)}
            response = requests.post(f"{API_BASE_URL}/entity/login", files=files)
            print("DEBUG: File sent to FastAPI endpoint.")  # Debug statement

            if response.status_code != 200:
                error = (
                    f"Login failed: {response.json().get('detail', 'Unknown error')}"
                )
                print(f"DEBUG: Login failed with error: {error}")  # Debug statement
                return render_template("login.html", error=error)

            # Process the response from the FastAPI endpoint
            data = response.json()
            flash(f"Login successful. Your DID: {data.get('did')}")
            session["did"] = data.get("did")
            print(f"DEBUG: Login successful. DID: {data.get('did')}")  # Debug statement

            # Redirect to the selection page after successful login
            return redirect(url_for("selection"))

        except Exception as e:
            error = f"Error during login: {str(e)}"
            print(f"DEBUG: Exception occurred: {error}")  # Debug statement

    print("DEBUG: Rendering login.html.")  # Debug statement
    return render_template("login.html", error=error)


# Registration: Send HSML data to the FastAPI /entity/register-user endpoint.
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        hsml_type = request.form.get("hsml_type")
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": hsml_type,
        }
        if hsml_type == "Person":
            hsml_obj["name"] = request.form.get("name").strip()
            hsml_obj["birthDate"] = request.form.get("birth_date").strip()
            hsml_obj["email"] = request.form.get("email").strip()
        elif hsml_type == "Organization":
            hsml_obj["name"] = request.form.get("org_name").strip()
            hsml_obj["description"] = request.form.get("description").strip()
        else:
            flash("Invalid HSML type selected for registration.")
            return redirect(url_for("register"))

        try:
            response = requests.post(
                f"{API_BASE_URL}/entity/register-user", json=hsml_obj, timeout=15
            )
        except Exception as e:
            flash(f"Registration service unreachable: {e}")
            return redirect(url_for("register"))

        if response.status_code == 200:
            data = response.json()
            did = data.get("did")
            private_key = data.get("private_key")
            private_key = private_key.replace("\\n", "\n").strip('"')
            if "private_key" in data:
                del data["private_key"]
            hsml_json_str = json.dumps(data.get("hsml", hsml_obj), indent=2)
            return render_template(
                "result.html", json_str=hsml_json_str, private_key=private_key, did=did
            )
        else:
            try:
                error_msg = response.json().get("detail", "")
            except ValueError:
                error_msg = response.text
            flash(f"Registration failed: {error_msg}")
            return redirect(url_for("register"))
    return render_template("register.html")


# Selection route: renders the selection page (index.html) where the user selects between Entity, Agent, and Credential.
@app.route("/selection")
def selection():
    return render_template("index.html")


# Entity creation route: renders entity.html on GET and processes form submissions on POST.
@app.route("/entity", methods=["GET", "POST"])
def create_entity():
    if request.method == "POST":
        hsml_obj = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Entity",
            "name": request.form.get("entity_name"),
            "description": request.form.get("description"),
        }
        registered_by = session.get("did")
        payload = {"entity": hsml_obj, "registered_by": registered_by}
        try:
            api_response = requests.post(
                f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15
            )
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(url_for("create_entity"))
        if api_response.status_code == 200:
            data = api_response.json()
            private_key = data.get("private_key", "")
            if "private_key" in data:
                del data["private_key"]
            hsml_json_str = json.dumps(data, indent=2)
            return render_template(
                "result.html",
                json_str=hsml_json_str,
                private_key=private_key,
                did=data.get("did", ""),
            )
        else:
            try:
                err_msg = api_response.json().get("detail", "")
            except ValueError:
                err_msg = api_response.text
            flash(f"Entity registration failed: {err_msg}")
            return redirect(url_for("create_entity"))
    return render_template("entity.html")


# Agent creation route: now expects creator subfields from the form.
@app.route("/create/agent", methods=["GET", "POST"])
def create_agent():
    if "did" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    kafka_topic = None

    if request.method == "POST":
        name = request.form.get("agent_name")
        description = request.form.get("agent_description")
        date_created = request.form.get("date_created")
        date_modified = request.form.get("date_modified")

        # Get creator details from user input rather than auto-populating.
        creator_name = request.form.get("creator_name")
        creator_type = request.form.get("creator_type")
        creator_id = request.form.get("creator_id")

        if (
            not name
            or not description
            or not date_created
            or not date_modified
            or not creator_name
            or not creator_type
            or not creator_id
        ):
            flash("Please provide all required fields.")
            return redirect(request.url)

        agent_json = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Agent",
            "name": name,
            "creator": {
                "@type": creator_type,
                "name": creator_name,
                "swid": creator_id,
            },
            "dateCreated": date_created,
            "dateModified": date_modified,
            "description": description,
        }

        content_url = request.form.get("content_url")
        if content_url:
            agent_json["contentURL"] = content_url

        payload = {"entity": agent_json, "registered_by": session.get("did")}

        try:
            response = requests.post(
                f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15
            )
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(request.url)

        if response.status_code == 200:
            data = response.json()
            private_key = data.get("private_key", "")
            kafka_topic = data.get("kafka_topic", "")
            print(f"DEBUG: Kafka topic: {kafka_topic}")
            if "private_key" in data:
                del data["private_key"]
            hsml_json_str = json.dumps(data.get("metadata", agent_json), indent=2)
            flash("Agent created successfully!")
            return render_template(
                "result.html",
                json_str=hsml_json_str,
                private_key=private_key,
                did=data.get("did"),
                kafka_topic=kafka_topic,
            )
        else:
            try:
                err_msg = response.json().get("detail", "Unknown error")
            except Exception:
                err_msg = response.text
            flash(f"Agent registration failed: {err_msg}")
            return redirect(request.url)

    return render_template("agent.html", kafka_topic=kafka_topic)


# Credential creation route: updated to reflect the new required and optional fields.
@app.route("/create/credential", methods=["GET", "POST"])
def create_credential():
    if "did" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    if request.method == "POST":
        # Required fields
        name = request.form.get("credential_name")
        description = request.form.get("credential_description")

        issuedBy_type = request.form.get("issuedBy_type")
        issuedBy_name = request.form.get("issuedBy_name")
        issuedBy_swid = request.form.get("issuedBy_swid")

        accessAuthorization_type = request.form.get("accessAuthorization_type")
        accessAuthorization_name = request.form.get("accessAuthorization_name")
        accessAuthorization_swid = request.form.get("accessAuthorization_swid")

        authorizedForDomain_type = request.form.get("authorizedForDomain_type")
        authorizedForDomain_name = request.form.get("authorizedForDomain_name")
        authorizedForDomain_swid = request.form.get("authorizedForDomain_swid")

        if not all(
            [
                name,
                description,
                issuedBy_type,
                issuedBy_name,
                issuedBy_swid,
                accessAuthorization_type,
                accessAuthorization_name,
                accessAuthorization_swid,
                authorizedForDomain_type,
                authorizedForDomain_name,
                authorizedForDomain_swid,
            ]
        ):
            flash("Please provide all required fields.")
            return redirect(request.url)

        # This should be Agent A's **private key** file
        if "pem_file" not in request.files:
            flash(
                "Please upload the private key (.pem) for the Agent being granted this Credential."
            )
            return redirect(request.url)

        pem_file = request.files["pem_file"]
        if pem_file.filename == "":
            flash("No private key file selected.")
            return redirect(request.url)

        # Build the credential JSON object.
        credential_json = {
            "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
            "@type": "Credential",
            "name": name,
            "description": description,
            "issuedBy": {
                "@type": issuedBy_type,
                "name": issuedBy_name,
                "swid": issuedBy_swid,
            },
            "accessAuthorization": {
                "@type": accessAuthorization_type,
                "name": accessAuthorization_name,
                "swid": accessAuthorization_swid,
            },
            "authorizedForDomain": {
                "@type": authorizedForDomain_type,
                "name": authorizedForDomain_name,
                "swid": authorizedForDomain_swid,
            },
        }

        registered_by = session.get("did")
        payload = {"entity": credential_json, "registered_by": registered_by}

        try:
            response = requests.post(
                f"{API_BASE_URL}/entity/register-entity", json=payload, timeout=15
            )
        except Exception as e:
            flash(f"Error contacting registration service: {e}")
            return redirect(request.url)

        if response.status_code == 200:
            data = response.json()
            private_key = data.get("private_key", "")
            if "private_key" in data:
                del data["private_key"]
            hsml_json_str = json.dumps(data.get("metadata", credential_json), indent=2)
            flash("Credential created successfully!")
            return render_template(
                "result.html",
                json_str=hsml_json_str,
                private_key=private_key,
                did=data.get("did"),
            )
        else:
            try:
                err_msg = response.json().get("detail", "Unknown error")
            except Exception:
                err_msg = response.text
            flash(f"Credential registration failed: {err_msg}")
            return redirect(request.url)

    return render_template("credential.html")


# Endpoint to download the private key as mykey.pem.
@app.route("/download_key")
def download_key():
    private_key = request.args.get("key")
    if not private_key:
        return "No key provided", 400
    response = make_response(private_key)
    response.headers["Content-Disposition"] = "attachment; filename=mykey.pem"
    response.headers["Content-Type"] = "application/octet-stream"
    return response


@app.route("/download_json")
def download_json():
    json_str = request.args.get("json_str")  # Get JSON string from the request
    if not json_str:
        return "No JSON data provided", 400

    try:
        # Parse the string into JSON and pretty-print it
        parsed_json = json.loads(json_str)
        formatted_json = json.dumps(
            parsed_json, indent=2
        )  # Ensures multi-line formatting
    except json.JSONDecodeError:
        return "Invalid JSON format", 400

    response = make_response(formatted_json)
    response.headers["Content-Disposition"] = "attachment; filename=entity_data.json"
    response.headers["Content-Type"] = "application/json"
    return response


if __name__ == "__main__":
    app.run(debug=True)
