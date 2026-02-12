"""
Wazuh Connector (Shared Library)
Provides unified authentication (Primary 55000 -> Fallback 443) and data querying
for all features (07-12). Credentials loaded from .env.
"""

import requests
import urllib3
import yaml
import os
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv
import sys

# Disable insecure https warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv() 

class ConfigLoader:
    @staticmethod
    def load_config(path: str = "src/feature7/config.yaml") -> dict:
        # Load yaml structure
        if not os.path.exists(path):
            abs_path = os.path.join(os.getcwd(), path)
            if not os.path.exists(abs_path):
                 clean_path = "c:/DR365/DR365V2/src/feature7/config.yaml"
                 if os.path.exists(clean_path):
                     path = clean_path
                 else:
                     return {}
            else:
                path = abs_path
            
        with open(path, 'r') as f:
            config = yaml.safe_load(f) or {}

        # Merge with .env variables (Env takes precedence for secrets)
        if 'wazuh' not in config: config['wazuh'] = {}
        if 'api' not in config['wazuh']: config['wazuh']['api'] = {}
        if 'dashboard' not in config['wazuh']: config['wazuh']['dashboard'] = {}

        config['wazuh']['host'] = os.getenv('WAZUH_HOST', config['wazuh'].get('host', ''))
        
        config['wazuh']['api']['user'] = os.getenv('WAZUH_API_USER', config['wazuh']['api'].get('user', ''))
        config['wazuh']['api']['password'] = os.getenv('WAZUH_API_PASSWORD', config['wazuh']['api'].get('password', ''))
        
        config['wazuh']['dashboard']['user'] = os.getenv('WAZUH_DASHBOARD_USER', config['wazuh']['dashboard'].get('user', ''))
        config['wazuh']['dashboard']['password'] = os.getenv('WAZUH_DASHBOARD_PASSWORD', config['wazuh']['dashboard'].get('password', ''))
        
        return config

class WazuhConnector:
    def __init__(self, config: dict):
        self.config = config
        self.host = self.config['wazuh']['host']
        self.api_token = None
        self.dash_cookies = None
        self.auth_method = None # 'api' or 'dashboard'
        
    def authenticate(self) -> bool:
        """Authenticate using Primary (55000) then Fallback (443)."""
        
        # 1. Try Primary: Standard API (55000)
        # Only try if we have credentials
        user_api = self.config['wazuh']['api'].get('user')
        pass_api = self.config['wazuh']['api'].get('password')
        
        if self.config['wazuh']['api'].get('enabled', False) and user_api and pass_api:
            port = self.config['wazuh']['api'].get('port', 55000)
            
            sys.stderr.write(f"[Auth] Attempting Primary API (Port {port})...\n")
            try:
                url = f"https://{self.host}:{port}/security/user/authenticate"
                resp = requests.get(url, auth=(user_api, pass_api), verify=False, timeout=5)
                
                if resp.status_code == 200:
                    self.api_token = resp.json().get('data', {}).get('token')
                    if self.api_token:
                        self.auth_method = 'api'
                        sys.stderr.write("[Auth] Primary API Success.\n")
                        return True
                else:
                    sys.stderr.write(f"[Auth] Primary API Failed: {resp.status_code}\n")
            except Exception as e:
                sys.stderr.write(f"[Auth] Primary API Error: {e}\n")

        # 2. Try Fallback: Dashboard Proxy (443)
        user_dash = self.config['wazuh']['dashboard'].get('user')
        pass_dash = self.config['wazuh']['dashboard'].get('password')

        if self.config['wazuh']['dashboard'].get('enabled', False) and user_dash and pass_dash:
            port = self.config['wazuh']['dashboard'].get('port', 443)
            
            sys.stderr.write(f"[Auth] Attempting Fallback Dashboard (Port {port})...\n")
            try:
                url = f"https://{self.host}:{port}/auth/login"
                payload = {"username": user_dash, "password": pass_dash}
                headers = {"kbn-xsrf": "true", "osd-xsrf": "true", "Content-Type": "application/json"}
                
                resp = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
                
                if resp.status_code == 200:
                    self.dash_cookies = resp.cookies
                    self.auth_method = 'dashboard'
                    sys.stderr.write("[Auth] Fallback Dashboard Success.\n")
                    return True
                else:
                    sys.stderr.write(f"[Auth] Fallback Dashboard Failed: {resp.status_code}\n")
            except Exception as e:
                sys.stderr.write(f"[Auth] Fallback Dashboard Error: {e}\n")
                
        return False


        return None

    def get_all_agents(self) -> List[Dict]:
        """Get all agents. Handles both auth methods."""
        agents = []
        if not self.auth_method:
            return []

        # PRIMARY STRATEGY (55000)
        if self.auth_method == 'api':
            url = f"https://{self.host}:{self.config['wazuh']['api']['port']}/agents"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            params = {"select": "id,name,ip,status,os", "limit": 100} # Fetch up to 100 agents
            
            try:
                resp = requests.get(url, headers=headers, params=params, verify=False)
                if resp.status_code == 200:
                    agents = resp.json().get('data', {}).get('affected_items', [])
            except Exception as e:
                sys.stderr.write(f"[API] Error getting agents: {e}\n")

        elif self.auth_method == 'dashboard':
            # Attempt to discover agents via aggregation on recent alerts
            # Writing to stderr to avoid breaking MCP JSON protocol
            sys.stderr.write("[Info] Attempting to discover agents via Dashboard Alerts Aggregation...\n")
            
            query = {
                "size": 0,
                "query": {
                    "range": { "@timestamp": { "gte": "now-24h" } }
                },
                "aggs": {
                    "unique_agents": {
                        "terms": {
                            "field": "agent.name",
                            "size": 50
                        },
                        "aggs": {
                            "agent_id": { "terms": { "field": "agent.id", "size": 1 } },
                            "agent_ip": { "terms": { "field": "agent.ip", "size": 1 } }
                        }
                    }
                }
            }
            
            resp = self._proxy_request("POST", "wazuh-alerts-*/_search", query)
            if resp and resp.status_code == 200:
                buckets = resp.json().get('aggregations', {}).get('unique_agents', {}).get('buckets', [])
                for b in buckets:
                    name = b['key']
                    id_bucket = b.get('agent_id', {}).get('buckets', [])
                    aid = id_bucket[0]['key'] if id_bucket else "unknown"
                    ip_bucket = b.get('agent_ip', {}).get('buckets', [])
                    ip = ip_bucket[0]['key'] if ip_bucket else "unknown"
                    
                    agents.append({
                        "id": aid,
                        "name": name,
                        "ip": ip,
                        "status": "active (inferred)",
                        "os": {"platform": "unknown"}
                    })
            
        return agents

    def get_agent(self, agent_name: str) -> Optional[Dict]:
        """Get agent ID by name. Handles both auth methods."""
        if not self.auth_method:
            return None
            
        sys.stderr.write(f"[API] Resolving agent: {agent_name} via {self.auth_method}\n")
        
        # PRIMARY STRATEGY (55000)
        if self.auth_method == 'api':
            url = f"https://{self.host}:{self.config['wazuh']['api']['port']}/agents"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            params = {"search": agent_name, "select": "id,name,ip,status,os"}
            
            try:
                resp = requests.get(url, headers=headers, params=params, verify=False)
                if resp.status_code == 200:
                    items = resp.json().get('data', {}).get('affected_items', [])
                    for item in items:
                        if item['name'] == agent_name:
                            return item
            except Exception as e:
                sys.stderr.write(f"[API] Error getting agent: {e}\n")

        # FALLBACK STRATEGY (443 - Dashboard Proxy)
        elif self.auth_method == 'dashboard':
            query = {
                "size": 1,
                "query": {
                    "match": { "agent.name": agent_name }
                },
                "_source": ["agent.id", "agent.name", "agent.ip"]
            }
            
            resp = self._proxy_request("POST", "wazuh-alerts-*/_search", query)
            if resp and resp.status_code == 200:
                hits = resp.json().get('hits', {}).get('hits', [])
                if hits:
                    agent_data = hits[0]['_source']['agent']
                    return {
                        "id": agent_data.get('id'),
                        "name": agent_data.get('name'),
                        "ip": agent_data.get('ip'),
                        "status": "active (derived)",
                        "os": {"platform": "unknown"}
                    }
                    
        return None

    def query_indexer(self, query: dict) -> List[Dict]:
        """Query the Indexer. Uses Dashboard Proxy if sticky cookie present."""
        if self.dash_cookies:
            return self._query_via_dashboard(query)
        print("[Warn] No Dashboard cookies available for Indexer query.")
        return []

    def _query_via_dashboard(self, query) -> List[Dict]:
        resp = self._proxy_request("POST", "wazuh-alerts-*/_search", query)
        if resp and resp.status_code == 200:
            return [h['_source'] for h in resp.json().get('hits', {}).get('hits', [])]
        return []

    def _proxy_request(self, method, path, json_data):
        url = f"https://{self.host}:{self.config['wazuh']['dashboard']['port']}/api/console/proxy"
        params = {"path": path, "method": method}
        headers = {"kbn-xsrf": "true", "osd-xsrf": "true", "Content-Type": "application/json"}
        return requests.post(url, params=params, json=json_data, cookies=self.dash_cookies, headers=headers, verify=False, timeout=20)
        
    def get_syscollector_processes(self, agent_id: str) -> List[Dict]:
        """Get processes. Requires Manager API (55000)."""
        if self.auth_method == 'api':
            url = f"https://{self.host}:{self.config['wazuh']['api']['port']}/syscollector/{agent_id}/processes"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            try:
                resp = requests.get(url, headers=headers, params={"limit": 500}, verify=False)
                if resp.status_code == 200:
                    return resp.json().get('data', {}).get('affected_items', [])
            except:
                pass
        return []
