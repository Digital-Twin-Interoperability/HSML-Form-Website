"""
           __n__n__
    .------`-\00/-'
   /  ##  ## (oo)
  / \## __   ./
     |//YY \|/
snd  |||   |||
"""

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
import mysql.connector as mysql
from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
import json, subprocess, os
from CLItool import extract_did_from_private_key  # Assumes CLItool provides DID extraction
from dotenv import load_dotenv

load_dotenv()  # Load .env file from the current directory

app = FastAPI()

# Database configuration from environment variables
db_config = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "did_registry")
}

# Kafka configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
try:
    admin_client = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP})
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})
except Exception as e:
    print(f"Kafka initialization error: {e}")
    admin_client = None
    producer = None

def connect_db():
    """Connect to the MySQL database using credentials in db_config."""
    try:
        return mysql.connect(**db_config)
    except mysql.Error as err:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {err}")

def create_kafka_topic(topic_name: str, num_partitions: int = 1, replication_factor: int = 1):
    """Create a Kafka topic for an Agent entity, if Kafka is configured."""
    if not admin_client:
        return
    topic_list = [NewTopic(topic_name, num_partitions=num_partitions, replication_factor=replication_factor)]
    try:
        fs = admin_client.create_topics(topic_list)
        for topic, future in fs.items():
            future.result()  # Wait for topic creation to complete
    except Exception as e:
        print(f"Kafka topic creation failed or already exists: {e}")

def send_kafka_message(topic: str, message: dict):
    """Send a JSON message to a Kafka topic, if Kafka is configured."""
    if not producer:
        return
    try:
        producer.produce(topic, json.dumps(message))
        producer.flush()
    except Exception as e:
        print(f"Kafka message send failed: {e}")

def register_entity_in_db(data: dict, registered_by: str, topic_name: str = None):
    """
    Common helper that inserts or replaces the entity in the database.
    """
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "REPLACE INTO did_keys (did, public_key, metadata, registered_by, kafka_topic) VALUES (%s, %s, %s, %s, %s)",
            (data["swid"], data["swid"].replace("did:key:", ""), json.dumps(data), registered_by, topic_name)
        )
        db.commit()
    except mysql.Error as err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database insert failed: {err}")
    finally:
        cursor.close()
        db.close()

def handle_credential_logic(data: dict, payload: dict, registered_by: str):
    """
    For Credential entities, verify required swid fields exist, validate the domain key,
    and update the authorized domain's metadata.
    """
    issued_by_did = data.get("issuedBy", {}).get("swid")
    auth_domain = data.get("authorizedForDomain", {})
    authorized_for_domain_did = auth_domain.get("swid")
    credential_domain_name = auth_domain.get("name")
    access_auth = data.get("accessAuthorization", {})
    access_auth_did = access_auth.get("swid")
    
    if not (issued_by_did and authorized_for_domain_did and access_auth_did):
        raise HTTPException(status_code=400, detail="Credential is missing required swid fields in issuedBy, authorizedForDomain, or accessAuthorization.")
    if issued_by_did != registered_by:
        raise HTTPException(status_code=403, detail="The 'issuedBy.swid' must match the user's DID.")
    
    domain_pem = payload.get("domain_pem")
    if not domain_pem:
        raise HTTPException(status_code=400, detail=f"Provide the private_key.pem content for '{credential_domain_name}' to verify domain access.")
    
    domain_pem_path = "/tmp/domain_key.pem"
    try:
        with open(domain_pem_path, "w") as f:
            f.write(domain_pem)
        credential_domain_did = extract_did_from_private_key(domain_pem_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid domain private key for '{credential_domain_name}': {e}")
    finally:
        try:
            os.remove(domain_pem_path)
        except OSError:
            pass
    if credential_domain_did != authorized_for_domain_did:
        raise HTTPException(status_code=403, detail="Domain private key does not match the provided authorizedForDomain DID.")
    
    db = connect_db()
    cur = db.cursor()
    cur.execute("SELECT metadata, allowed_did FROM did_keys WHERE did = %s", (authorized_for_domain_did,))
    domain_rec = cur.fetchone()
    if not domain_rec:
        cur.close()
        db.close()
        raise HTTPException(status_code=400, detail=f"Domain DID {authorized_for_domain_did} not found. Register '{credential_domain_name}' first.")
    
    domain_metadata = json.loads(domain_rec[0])
    if "canAccess" not in domain_metadata:
        domain_metadata["canAccess"] = [access_auth]
    else:
        existing_access = domain_metadata.get("canAccess")
        if not isinstance(existing_access, list):
            existing_access = [existing_access]
        existing_swids = {entry.get("swid") for entry in existing_access if isinstance(entry, dict)}
        if access_auth_did not in existing_swids:
            existing_access.append(access_auth)
        domain_metadata["canAccess"] = existing_access
    
    allowed_did_list = domain_rec[1].split(",") if domain_rec[1] else []
    if access_auth_did and access_auth_did not in allowed_did_list:
        allowed_did_list.append(access_auth_did)
    allowed_did_str = ",".join(allowed_did_list)
    try:
        cur.execute("UPDATE did_keys SET metadata = %s, allowed_did = %s WHERE did = %s",
                    (json.dumps(domain_metadata), allowed_did_str, authorized_for_domain_did))
        db.commit()
    except mysql.Error as err:
        db.rollback()
        cur.close()
        db.close()
        raise HTTPException(status_code=500, detail=f"Failed to update domain access: {err}")
    cur.close()
    db.close()

def generate_did_key():
    """Generate a unique DID:key and return (did, private_key_pem)."""
    result = subprocess.run(["python", "CLItool.py", "--export-private"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("CLI tool did not execute properly.")
    output_lines = result.stdout.splitlines()
    did_key = None
    for line in output_lines:
        if line.startswith("Generated DID:key:"):
            did_key = line.split("Generated DID:key:")[1].strip()
            break
    if not did_key:
        raise RuntimeError("Failed to parse DID from CLI output.")
    try:
        with open("private_key.pem", "r") as key_file:
            private_key_pem = key_file.read()
    except FileNotFoundError:
        raise RuntimeError("Private key file not found after DID generation.")
    try:
        os.remove("private_key.pem")
    except OSError:
        pass
    return did_key, private_key_pem

@app.post("/login")
async def login_user(pem_file: UploadFile = File(...)):
    """
    Authenticate a user by their private key (.pem file).
    The .pem file is used to extract the DID and verify it exists in the registry.
    """
    pem_content = await pem_file.read()
    if not pem_content:
        raise HTTPException(status_code=400, detail="Empty .pem file received.")
    temp_path = f"/tmp/{pem_file.filename}"
    try:
        with open(temp_path, "wb") as temp_pem:
            temp_pem.write(pem_content)
        user_did = extract_did_from_private_key(temp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading .pem file: {e}")
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    db = connect_db()
    cursor = db.cursor()
    cursor.execute("SELECT metadata FROM did_keys WHERE did = %s", (user_did,))
    result = cursor.fetchone()
    cursor.close()
    db.close()
    if not result:
        raise HTTPException(status_code=401, detail="DID not found. Please register first.")
    try:
        user_data = json.loads(result[0])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupt user data in database.")
    if user_data.get("@type") not in ["Person", "Organization"]:
        raise HTTPException(status_code=403, detail="Only Person or Organization DIDs can be used for login.")
    return {"status": "success", "did": user_did, "name": user_data.get("name")}

@app.post("/register")
async def register_user(data: dict):
    """
    Register a new user (Person or Organization) with the provided HSML JSON data.
    Expects `data` to include required fields for Person/Organization.
    """
    entity_type = data.get("@type")
    if entity_type not in ["Person", "Organization"]:
        raise HTTPException(status_code=400, detail="Can only register a Person or Organization as a new user.")
    if entity_type == "Person":
        required_fields = ["name", "birthDate", "email"]
    else:
        required_fields = ["name", "description"]
    missing = [field for field in required_fields if field not in data or data[field] == ""]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")
    if "@context" not in data:
        data["@context"] = "https://digital-twin-interoperability.github.io/hsml-schema-context/hsml.jsonld"

    try:
        did_key, private_key_pem = generate_did_key()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating DID: {e}")
    data["swid"] = did_key

    db = connect_db()
    cursor = db.cursor()
    registered_by = did_key
    try:
        cursor.execute(
            "REPLACE INTO did_keys (did, public_key, metadata, registered_by, kafka_topic) VALUES (%s, %s, %s, %s, %s)",
            (did_key, did_key.replace("did:key:", ""), json.dumps(data), registered_by, None)
        )
        db.commit()
    except mysql.Error as err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database insert failed: {err}")
    finally:
        cursor.close()
        db.close()
    return {"status": "success", "did": did_key, "private_key": private_key_pem, "hsml": data}

@app.post("/register_entity")
async def register_entity_endpoint(payload: dict):
    """
    Register a new HSML entity (Agent, Credential, etc.) after user login.
    Expected JSON payload should include:
      - "entity": HSML JSON object of the entity to register.
      - "registered_by": DID of the user performing the registration.
      - For Credential entities, "domain_pem": private key (PEM content) of the domain for verification.
    """
    if "entity" not in payload:
        raise HTTPException(status_code=400, detail="No entity data provided.")
    data = payload["entity"]
    registered_by = payload.get("registered_by")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Entity data must be a JSON object.")
    if "@context" not in data or "hsml.jsonld" not in data["@context"]:
        raise HTTPException(status_code=400, detail="Not a valid HSML JSON (missing @context).")
    entity_type = data.get("@type")
    if not entity_type:
        raise HTTPException(status_code=400, detail="Missing '@type' in entity data.")
    required_fields_map = {
        "Entity": ["name", "description"],
        "Person": ["name", "birthDate", "email"],
        "Agent": ["name", "creator", "dateCreated", "dateModified", "description"],
        "Credential": ["name", "description", "issuedBy", "accessAuthorization", "authorizedForDomain"],
        "Organization": ["name", "description", "url", "address", "logo", "foundingDate", "email"]
    }
    required_fields = required_fields_map.get(entity_type)
    if not required_fields:
        raise HTTPException(status_code=400, detail=f"Unsupported or unknown entity type: {entity_type}")
    missing_fields = [field for field in required_fields if field not in data or data[field] == ""]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_fields}")
    if entity_type in ["Person", "Organization"] and not registered_by:
        registered_by = None
    if entity_type not in ["Person", "Organization"]:
        if not registered_by:
            raise HTTPException(status_code=401, detail="Authentication required to register this entity.")
        db = connect_db()
        cur = db.cursor()
        cur.execute("SELECT metadata FROM did_keys WHERE did = %s", (registered_by,))
        reg_user = cur.fetchone()
        cur.close()
        db.close()
        if not reg_user:
            raise HTTPException(status_code=401, detail="Registered_by DID not found. Login required.")
        reg_user_data = json.loads(reg_user[0])
        if reg_user_data.get("@type") not in ["Person", "Organization"]:
            raise HTTPException(status_code=403, detail="Only a Person or Organization can register new entities.")
    if "swid" in data:
        pass  # Ignore provided swid, generate a new one.
    if entity_type == "Credential":
        handle_credential_logic(data, payload, registered_by)
    topic_name = None
    if entity_type == "Agent":
        topic_name = data["name"].replace(" ", "_").lower()
        create_kafka_topic(topic_name)
        send_kafka_message(topic_name, {"message": f"New Agent registered: {data['name']}"})
    try:
        did_key, private_key_pem = generate_did_key()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate DID for entity: {e}")
    data["swid"] = did_key
    public_key_part = did_key.replace("did:key:", "")
    if not registered_by:
        registered_by = did_key
    register_entity_in_db(data, registered_by, topic_name)
    response_data = {
        "status": "success",
        "did": did_key,
        "entity_type": entity_type,
        "metadata": data
    }
    if entity_type not in ["Credential"]:
        response_data["private_key"] = private_key_pem
    return JSONResponse(status_code=200, content=response_data)
