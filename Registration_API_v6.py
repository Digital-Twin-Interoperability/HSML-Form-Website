import json
import os
import subprocess

# -----------------------------
# Dummy / Placeholder Implementations
# -----------------------------
# Dummy MySQL connector placeholder
class DummyCursor:
    def execute(self, query, params=None):
        print(f"[Dummy MySQL] Executing query: {query} with params: {params}")
    def fetchone(self):
        # Always simulate no existing record (i.e. 0 count)
        return [0]

class DummyDB:
    def cursor(self):
        return DummyCursor()
    def commit(self):
        print("[Dummy MySQL] Commit simulated.")
    def close(self):
        print("[Dummy MySQL] Connection closed.")

class DummyMySQLConnector:
    @staticmethod
    def connect(**db_config):
        print(f"[Dummy MySQL] Connecting with config: {db_config}")
        return DummyDB()

# Dummy Kafka placeholders
class DummyFuture:
    def __init__(self, topic):
        self.topic = topic
    def result(self):
        print(f"[Dummy Kafka] Simulated topic creation result for: {self.topic}")

class DummyAdminClient:
    def __init__(self, config):
        self.config = config
        print(f"[Dummy Kafka] AdminClient configured with: {config}")
    def create_topics(self, topic_list):
        print(f"[Dummy Kafka] Simulated creation of topics: {[t.topic for t in topic_list]}")
        return {topic.topic: DummyFuture(topic.topic) for topic in topic_list}

class DummyProducer:
    def __init__(self, config):
        self.config = config
        print(f"[Dummy Kafka] Producer configured with: {config}")
    def produce(self, topic, message):
        print(f"[Dummy Kafka] Simulated message sent to topic '{topic}': {message}")
    def flush(self):
        print("[Dummy Kafka] Flush simulated.")

# Dummy NewTopic to simulate Kafka topic creation
class DummyNewTopic:
    def __init__(self, topic, num_partitions, replication_factor):
        self.topic = topic
        self.num_partitions = num_partitions
        self.replication_factor = replication_factor

# -----------------------------
# Substitutions for real libraries
# -----------------------------
# Instead of using mysql.connector and confluent_kafka,
# we substitute them with our dummy implementations.
mysql_connector = DummyMySQLConnector
AdminClient = DummyAdminClient
Producer = DummyProducer
NewTopic = DummyNewTopic

# Import the extract_did_from_private_key from CLItool.py (unchanged)
from CLItool import extract_did_from_private_key

# -----------------------------
# Original Registration Code (with placeholders)
# -----------------------------
# Kafka Configuration
KAFKA_CONFIG = {
    "bootstrap.servers": "localhost:9092"
}
admin_client = AdminClient(KAFKA_CONFIG)
producer = Producer(KAFKA_CONFIG)

# MySQL Database Configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "MoonwalkerJPL85!",
    "database": "did_registry"
}

# Connect to MySQL
def connect_db():
    return mysql_connector.connect(**db_config)

# Function to create a Kafka topic for Agents
def create_kafka_topic(topic_name, num_partitions=1, replication_factor=1):
    """Creates a Kafka topic using DummyAdminClient"""
    topic_list = [NewTopic(topic_name, num_partitions=num_partitions, replication_factor=replication_factor)]
    fs = admin_client.create_topics(topic_list)
    
    for topic, f in fs.items():
        try:
            f.result()  # Simulate waiting for topic creation
            print(f"Kafka topic '{topic}' created successfully (simulated).")
        except Exception as e:
            print(f"Failed to create topic '{topic}': {e}")

# Function to send a Kafka message
def send_kafka_message(topic, message):
    """Sends a message to a Kafka topic (simulated)"""
    try:
        producer.produce(topic, json.dumps(message))
        producer.flush()
        print(f"Message sent to Kafka topic '{topic}' (simulated): {message}")
    except Exception as e:
        print(f"Failed to send message to Kafka topic '{topic}': {e}")

# Function to generate DID:key using CLI tool (modified)
def generate_did_key():
    """Runs the CLI tool to generate a unique DID:key and extract the private key"""
    while True:
        result = subprocess.run(["python", "CLItool.py", "--export-private"], capture_output=True, text=True)
        print(f"Subprocess output:\n{result.stdout}")  # Debug output
        output = result.stdout.splitlines()
        
        # Extract DID:key from the stdout (terminal output)
        did_key = None
        for line in output:
            if line.startswith("Generated DID:key:"):
                did_key = line.split("Generated DID:key:")[1].strip()
        
        if not did_key:
            raise ValueError("Failed to generate DID:key from output")

        # Now, read the private key from the saved file "private_key.pem"
        private_key_path = "private_key.pem"
        try:
            with open(private_key_path, "rb") as key_file:
                private_key = key_file.read()  # Read the private key as bytes
        except FileNotFoundError:
            raise ValueError(f"Private key file '{private_key_path}' not found")
        
        # Check if the generated swid already exists in the database
        db = connect_db()
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM did_keys WHERE did = %s", (did_key,))
        if cursor.fetchone()[0] == 0:  # SWID is unique
            # Return DID:key and private key as a PEM string
            return did_key, private_key.decode("utf-8")

# Function for login before registering
def login_or_register():
    choice = input("Must be registered in the Spatial Web to register a new Entity. Type 'new' to register or 'login' if already registered: ")
    db = connect_db()
    cursor = db.cursor()
    if choice.lower() == "new":
        print("Registering a new user. You can only register a Person or Organization.")
        return None
    elif choice.lower() == "login":
        private_key_path = input("Provide your private_key.pem path: ")
        user_did = extract_did_from_private_key(private_key_path)
        cursor.execute("SELECT metadata FROM did_keys WHERE did = %s", (user_did,))
        result = cursor.fetchone()
        if not result:
            print("DID not found in database. Please register first.")
            return None
        user_data = json.loads(result[0])
        if user_data.get("@type") not in ["Person", "Organization"]:
            print("Only registered Persons or Organizations can register new entities.")
            return None
        print(f"Welcome {user_data.get('name')}, you can now register your new Entity.")
        return user_did
    else:
        print("Invalid choice.")
        return None

# Function to validate JSON and register entity
def register_entity(json_file_path, output_directory, registered_by=None):
    """Validates, registers, and stores an HSML entity"""
    try:
        with open(json_file_path, "r") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON format"}
    
    if not isinstance(data, dict):
        return {"status": "error", "message": "Uploaded file is not a valid JSON object"}

    if "@context" not in data or "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld" not in data["@context"]:
        return {"status": "error", "message": "Not a valid HSML JSON"}

    print("HSML JSON accepted.")

    entity_type = data.get("@type")
    required_fields = {
        "Entity": ["name", "description"],
        "Person": ["name", "birthDate", "email"],
        "Agent": ["name", "creator", "dateCreated", "dateModified", "description"],
        "Credential": ["name", "description", "issuedBy", "accessAuthorization", "authorizedForDomain"],
        "Organization": ["name", "description", "url", "address", "logo", "foundingDate", "email"]
    }
    
    if entity_type not in required_fields:
        return {"status": "error", "message": "Unknown or missing entity type"}

    missing_fields = [field for field in required_fields[entity_type] if field not in data]
    if missing_fields:
        return {"status": "error", "message": f"Missing required fields: {missing_fields}"}

    if entity_type == "Person" and "affiliation" not in data:
        print("Warning: 'affiliation' field is missing.")
    if entity_type == "Credential" and ("validFrom" not in data or "validUntil" not in data):
        print("Warning: Credential has no expiration date.")
    if entity_type == "Entity" and "linkedTo" not in data:
        print("Warning: Object not linked to any other Entity. It will be registered under this user’s SWID.")

    swid = data.get("swid")
    if swid:
        cursor = connect_db().cursor()
        cursor.execute("SELECT COUNT(*) FROM did_keys WHERE did = %s", (swid,))
        existing = cursor.fetchone()[0]
        if existing:
            print(f"Warning: The provided 'swid' ({swid}) already exists in the database. You should not register an already existing object.")
            user_input = input("Do you want to continue and overwrite the existing 'swid' property? (yes/no): ").strip().lower()
            if user_input != "yes":
                print("Process aborted. No changes were made.")
                exit()
        print(f"Warning: SWID '{swid}' in JSON file will be overwritten.")

    did_key, private_key = generate_did_key()
    data["swid"] = did_key
    print(f"Generated unique SWID: {did_key}")
    public_key_part = did_key.replace("did:key:", "")
        
    db = connect_db()
    cursor = db.cursor()

    if registered_by is None:
        registered_by = did_key

    topic_name = None
    if entity_type == "Agent":
        topic_name = data["name"].replace(" ", "_").lower()
        create_kafka_topic(topic_name)
        send_kafka_message(topic_name, {"message": f"New Agent registered: {data['name']}"})

    if entity_type == "Credential":
        issued_by_did = data.get("issuedBy", {}).get("swid")
        authorized_for_domain_did = data.get("authorizedForDomain", {}).get("swid")
        credential_domain_name = data.get("authorizedForDomain", {}).get("name")
        access_authorization_did = data.get("accessAuthorization", {}).get("swid")
        if not (issued_by_did and authorized_for_domain_did and access_authorization_did):
            raise ValueError("Missing required 'swid' in Credential fields")
        if issued_by_did != registered_by:
            raise ValueError("issuedBy field must match the User registering the Credential")
        private_key_path_credential_domain = input(f"Provide your private_key.pem path for '{credential_domain_name}' this Credential is giving access to: ")
        credential_domain_did = extract_did_from_private_key(private_key_path_credential_domain)
        if credential_domain_did != authorized_for_domain_did:
            print(f"Invalid private_key.pem for '{credential_domain_name}'")
            return None
        
        cursor.execute("SELECT metadata FROM did_keys WHERE did = %s", (authorized_for_domain_did,))
        domain_did_result = cursor.fetchone()
        if not domain_did_result:
            print(f"DID not found in database. Please register '{credential_domain_name}' first.")
            return None

        domain_data = json.loads(domain_did_result[0])
        new_access_auth = data.get("accessAuthorization", {})
        if "canAccess" not in domain_data:
            domain_data["canAccess"] = [new_access_auth]
        else:
            existing_can_access = domain_data.get("canAccess", [])
            if not isinstance(existing_can_access, list):
                existing_can_access = [existing_can_access]
            existing_swids = {entry["swid"] for entry in existing_can_access if "swid" in entry}
            if new_access_auth.get("swid") and new_access_auth["swid"] not in existing_swids:
                existing_can_access.append(new_access_auth)
            else:
                print(f"{new_access_auth.get('swid')} already has access to '{credential_domain_name}'")
            domain_data["canAccess"] = existing_can_access
        
        cursor.execute("UPDATE did_keys SET metadata = %s WHERE did = %s", (json.dumps(domain_data), authorized_for_domain_did))
        domain_json_output = os.path.join(output_directory, f"{domain_data['name'].replace(' ', '_')}.json")
        with open(domain_json_output, "w") as json_file:
            json.dump(data, json_file, indent=4)
        print(f"Updated {credential_domain_name} JSON saved to: {domain_json_output}")
        
        cursor.execute("SELECT allowed_did FROM did_keys WHERE did = %s", (authorized_for_domain_did,))
        allowed_did_result = cursor.fetchone()
        if allowed_did_result and allowed_did_result[0]:
            allowed_did_list = allowed_did_result[0].split(",")
        else:
            allowed_did_list = []
        new_did = new_access_auth.get("swid")
        if new_did and new_did not in allowed_did_list:
            allowed_did_list.append(new_did)
        allowed_did_string = ",".join(allowed_did_list)
        cursor.execute("UPDATE did_keys SET allowed_did = %s WHERE did = %s", (allowed_did_string, authorized_for_domain_did))

    cursor.execute(
        "REPLACE INTO did_keys (did, public_key, metadata, registered_by, kafka_topic) VALUES (%s, %s, %s, %s, %s)",
        (did_key, public_key_part, json.dumps(data), registered_by, topic_name)
    )
    db.commit()
    db.close()

    private_key_output = os.path.join(output_directory, "private_key.pem")
    json_output = os.path.join(output_directory, f"{data['name'].replace(' ', '_')}.json")

    with open(private_key_output, "w") as private_key_file:
        private_key_file.write(private_key)
    with open(json_output, "w") as json_file:
        json.dump(data, json_file, indent=4)

    print(f"Private key saved to: {private_key_output}")
    print(f"Updated JSON saved to: {json_output}")

    return {
        "status": "success",
        "message": "Entity registered successfully",
        "did_key": did_key,
        "private_key_path": private_key_output,
        "updated_json_path": json_output
    }

# Example usage
if __name__ == "__main__":
    user_did = login_or_register()
    if user_did is not None:
        json_file_path = input("Enter the directory to your HSML JSON to be registered: ")
        output_directory = "C:/Users/abarrio/OneDrive - JPL/Desktop/Digital Twin Interoperability/Codes/HSML Examples/registeredExamples"
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        result = register_entity(json_file_path, output_directory, registered_by=user_did)
        print(result)
    else:
        while True:
            json_file_path = input("Enter the directory to your Person/Organization HSML JSON to be registered: ")
            try:
                with open(json_file_path, "r") as file:
                    data = json.load(file)
            except json.JSONDecodeError:
                print("Error: Invalid JSON format.")
                continue 
            if data.get("@type") not in ["Person", "Organization"]:
                print("Error: You can only register a Person or Organization as a new user.")
                continue
            break
        output_directory = "C:/Users/abarrio/OneDrive - JPL/Desktop/Digital Twin Interoperability/Codes/HSML Examples/registeredExamples"
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        result = register_entity(json_file_path, output_directory, registered_by=None)
        print(result)
