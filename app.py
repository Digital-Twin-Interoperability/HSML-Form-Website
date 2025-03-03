from flask import Flask, render_template, request
import json

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        hsml_type = request.form.get('hsml_type')
        # If a type other than Person is selected, alert the user.
        if hsml_type != 'Person':
            return '''
            <script>
                alert("This functionality is currently being developed. Check back later!");
                window.location.href = "/";
            </script>
            '''
        # Process the Person form submission.
        name = request.form.get('name')
        birth_date = request.form.get('birth_date')
        email = request.form.get('email')
        
        # Build the HSML JSON object. Only include fields with values.
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

        json_str = json.dumps(hsml_obj, indent=2)
        return render_template("result.html", json_str=json_str)
    return render_template("index.html")

if __name__ == '__main__':
    app.run(debug=True)
