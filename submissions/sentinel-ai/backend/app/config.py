import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    APP_NAME: str = "SENTINEL AI"
    APP_TAGLINE: str = "Detect Early. Analyse Smartly. Defend Strongly."
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # IBM Db2 Configuration
    DB2_DATABASE: str = os.getenv("DB2_DATABASE", "SENTINEL")
    DB2_HOSTNAME: str = os.getenv("DB2_HOSTNAME", "localhost")
    DB2_PORT: int = int(os.getenv("DB2_PORT", "50000"))
    DB2_PROTOCOL: str = os.getenv("DB2_PROTOCOL", "TCPIP")
    DB2_UID: str = os.getenv("DB2_UID", "")
    DB2_PWD: str = os.getenv("DB2_PWD", "")
    DB2_SECURITY: str = os.getenv("DB2_SECURITY", "SSL")
    
    # IBM watsonx.ai Configuration
    WATSONX_APIKEY: str = os.getenv("WATSONX_APIKEY", "")
    WATSONX_PROJECT_ID: str = os.getenv("WATSONX_PROJECT_ID", "")
    WATSONX_URL: str = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    WATSONX_MODEL_ID: str = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")
    
    # Authentication & Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sentinel-defence-cyber-sec-key-2026")
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "SentinelAdmin2026!")

settings = Settings()

