from flask import Flask, render_template, request
import json

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        hsml_type = request.form.get('hsml_type')
        if hsml_type not in ['Person', 'Entity']:
            # If an unsupported type is submitted, alert the user.
            return '''
            <script>
                alert("This functionality is currently being developed. Check back later!");
                window.location.href = "/";
            </script>
            '''
        if hsml_type == 'Person':
            name = request.form.get('name')
            birth_date = request.form.get('birth_date')
            email = request.form.get('email')
            hsml_obj = {
                "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
                "@type": "Person"
            }
            if name:
                hsml_obj["name"] = name
            if birth_date:
                hsml_obj["birthDate"] = birth_date
            if email:
                hsml_obj["email"] = email
        elif hsml_type == 'Entity':
            name = request.form.get('entity_name')
            description = request.form.get('description')
            hsml_obj = {
                "@context": "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld",
                "@type": "Entity"
            }
            if name:
                hsml_obj["name"] = name
            if description:
                hsml_obj["description"] = description
            # swid is intentionally left out.
        json_str = json.dumps(hsml_obj, indent=2)
        return render_template("result.html", json_str=json_str)
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)
