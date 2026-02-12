
import psycopg2
import psycopg2.extras
import yaml
import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

def load_db_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load database configuration from config.yaml and override with .env.
    Defaults to looking in src/feature1/config.yaml if not specified.
    """
    if not config_path:
        # Determine absolute path relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to src, then into feature1
        default_path = os.path.join(current_dir, '..', 'feature1', 'config.yaml')
        config_path = os.path.normpath(default_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            db_config = config.get('database', {})
            
            # Override with environment variables if present
            db_config['host'] = os.getenv('DB_HOST', db_config.get('host'))
            db_config['port'] = os.getenv('DB_PORT', db_config.get('port', 5432))
            db_config['database'] = os.getenv('DB_NAME', db_config.get('database'))
            db_config['user'] = os.getenv('DB_USER', db_config.get('user'))
            db_config['password'] = os.getenv('DB_PASSWORD', db_config.get('password'))
            
            return db_config
    except Exception as e:
        logger.error(f"Failed to load DB config: {e}")
        raise

def get_db_connection():
    """Establish and return a database connection using config.yaml credentials."""
    db_config = load_db_config()
    
    # Ensure all required keys are present
    required_keys = ['host', 'port', 'database', 'user', 'password']
    missing = [k for k in required_keys if k not in db_config]
    if missing:
        raise ValueError(f"Missing database config keys: {missing}")

    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise RuntimeError(f"Could not connect to database: {e}")
