# auth.py (robust version)
import os, json, logging
from typing import Optional, Dict, Any, List

_logger = logging.getLogger(__name__)

# Lazy import helpers
def try_import(name: str):
    try:
        module = __import__(name)
        return module
    except Exception as e:
        _logger.warning("Optional import failed: %s -> %s", name, e)
        return None

# Try lazy imports
pymongo = try_import("pymongo")
bcrypt = try_import("bcrypt")
import streamlit as st

# If bcrypt is missing we will use a not-very-secure fallback for development only.
def _hash_pw(password: str) -> str:
    if bcrypt:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # fallback (NOT for production): prefix the password so stored value isn't plain
    return "devhash$" + password

def _check_pw(password: str, stored: str) -> bool:
    if bcrypt and stored and stored.startswith("$2b$") or (bcrypt and stored.startswith("$2a$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    if stored and stored.startswith("devhash$"):
        return stored == "devhash$" + password
    return False

class AuthManager:
    def __init__(self, local_store: str = "local_users.json"):
        self.local_store = os.path.abspath(local_store)
        self.users_collection = None
        self._use_mongo = False

        if pymongo:
            try:
                mongo_conf = st.secrets.get("mongo", None)
                if mongo_conf and "uri" in mongo_conf and mongo_conf["uri"]:
                    client = pymongo.MongoClient(mongo_conf["uri"], serverSelectionTimeoutMS=5000)
                    client.server_info()  # verify connection
                    db_name = mongo_conf.get("db", "customer_dashboard")
                    db = client.get_database(db_name)
                    self.users_collection = db["users"]
                    self._use_mongo = True
                    _logger.info("Auth: connected to MongoDB")
            except Exception as e:
                _logger.warning("Auth: MongoDB init failed: %s", e)
                self._use_mongo = False

        # ensure local file exists
        if not os.path.exists(self.local_store):
            with open(self.local_store, "w", encoding="utf-8") as f:
                json.dump([], f)

        # create default admin in local store if none exist (only local fallback)
        if not self._use_mongo:
            users = self._read_local()
            if not users:
                self.create_user("admin", "admin123", role="admin")

    def _read_local(self) -> List[Dict[str, Any]]:
        try:
            with open(self.local_store, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_local(self, data: List[Dict[str, Any]]) -> None:
        with open(self.local_store, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def create_user(self, username: str, password: str, role: str = "user") -> None:
        if not username or not password:
            raise ValueError("username and password are required")
        username = username.strip()
        hashed = _hash_pw(password)
        user_doc = {"username": username, "password": hashed, "role": role}
        if self._use_mongo and self.users_collection is not None:
            if self.users_collection.count_documents({"username": username}) > 0:
                raise ValueError("user exists")
            self.users_collection.insert_one(user_doc)
            return
        data = self._read_local()
        if any(u.get("username") == username for u in data):
            raise ValueError("user exists")
        data.append(user_doc)
        self._write_local(data)

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        if not username or not password:
            return None
        username = username.strip()
        if self._use_mongo and self.users_collection is not None:
            doc = self.users_collection.find_one({"username": username})
            if not doc: return None
            if _check_pw(password, doc.get("password", "")):
                return {"username": doc.get("username"), "role": doc.get("role", "user")}
            return None
        data = self._read_local()
        doc = next((u for u in data if u.get("username") == username), None)
        if not doc: return None
        if _check_pw(password, doc.get("password", "")):
            return {"username": doc.get("username"), "role": doc.get("role", "user")}
        return None

    def list_users(self):
        if self._use_mongo and self.users_collection is not None:
            return list(self.users_collection.find({}, {"password": 0, "_id": 0}))
        data = self._read_local()
        return [{"username": u.get("username"), "role": u.get("role")} for u in data]
