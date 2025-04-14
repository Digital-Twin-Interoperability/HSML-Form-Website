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