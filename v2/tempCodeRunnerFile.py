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