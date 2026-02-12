import requests
import json
import os
import logging
from typing import Dict, List, Optional, Any
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("feature13")

class StoneFlyClient:
    """
    Client for interacting with StoneFly Storage Concentrator REST API.
    """
    def __init__(self, base_url: str = None, username: str = None, password: str = None):
        self.base_url = base_url or os.getenv('STONEFLY_URL')
        self.username = username or os.getenv('STONEFLY_USER')
        self.password = password or os.getenv('STONEFLY_PASS')
        if not self.base_url:
            raise ValueError("STONEFLY_URL environment variable must be set")
        if not self.username:
            raise ValueError("STONEFLY_USER environment variable must be set")
        if not self.password:
            raise ValueError("STONEFLY_PASS environment variable must be set")
        self.session = requests.Session()
        self.session.verify = False  # Ignore SSL errors for internal appliance
        
        # Set Basic Auth and Default Headers
        self.session.auth = (self.username, self.password)
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Helper for GET requests."""
        url = f"{self.base_url.rstrip('/')}{endpoint}"
        
        # Ensure 'fmt=json' is always present
        if params is None:
            params = {}
        params['fmt'] = 'json'
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Debug: Check content type if needed
            # logger.info(f"Response Content-Type: {response.headers.get('Content-Type')}")
            
            return response.json()
        except requests.exceptions.JSONDecodeError:
            # Fallback for debugging: Print raw response if JSON fails
            logger.error(f"Failed to parse JSON from {url}")
            logger.error(f"Raw Response Response: {response.text[:500]}") # Log first 500 chars
            raise Exception(f"Invalid JSON response from appliance. Raw: {response.text[:100]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed to {url}: {e}")
            raise

    def get_system_info(self) -> Dict:
        """Get system details."""
        return self._get('/api/sys')

    def get_iscsi_volumes(self) -> List[Dict]:
        """List iSCSI volumes."""
        data = self._get('/api/iscsi_volume')
        return data.get('data', {}).get('iscsi_volumes', [])

    def get_nas_volumes(self) -> List[Dict]:
        """List NAS volumes."""
        data = self._get('/api/nas_volume')
        return data.get('data', {}).get('nas_volumes', [])

    def get_iscsi_volume_details(self, name: str) -> Dict:
        """Get details for a specific iSCSI volume."""
        data = self._get(f'/api/iscsi_volume/{name}')
        return data.get('data', {}).get('iscsi_volume_details', {})

    def get_nas_volume_details(self, name: str) -> Dict:
        """Get details for a specific NAS volume."""
        data = self._get(f'/api/nas_volume/{name}')
        return data.get('data', {}).get('nas_volume_details', {})

    def get_event_logs(self, severity: str = 'all', limit: int = 50, days: int = 7) -> List[Dict]:
        """
        Retrieve event logs.
        args:
            severity: 'warn', 'crit', or 'all'
            limit: max events to return
        """
        params = {
            'fmt': 'json',
            'limit': limit,
            'severity': severity,
            'order': 'desc'
        }
        data = self._get('/api/sys/eventlog', params=params)
        return data.get('data', {}).get('log_events', [])

def get_stonefusion_events(severity: str = 'all', limit: int = 20) -> str:
    """
    MCP Tool: Connects to StoneFly and retrieves event logs.
    """
    try:
        client = StoneFlyClient()
        events = client.get_event_logs(severity=severity, limit=limit)
        sys_info = client.get_system_info()
        sc_info = sys_info.get('data', {}).get('SC_info', {})
        
        response = {
            "feature": "Feature 13: StoneFusion Integration",
            "storage_appliance": {
                "name": sc_info.get("SC_Name", "Unknown"),
                "ip": sc_info.get("SC_LAN_IP", "Unknown"),
                "status": sc_info.get("SC_Status", "Unknown"),
                "uptime_seconds": sc_info.get("SC_Uptime_Secs", 0)
            },
            "events_retrieved": len(events),
            "filters": {"severity": severity, "limit": limit},
            "recent_events": events
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error in get_stonefusion_events: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)

def get_stonefusion_inventory() -> str:
    """
    MCP Tool: Retrieves a comprehensive inventory of all iSCSI and NAS volumes.
    """
    try:
        client = StoneFlyClient()
        
        # Parallel fetch could be better but sequential is safer for simple scripts
        iscsi_vols = client.get_iscsi_volumes()
        nas_vols = client.get_nas_volumes()
        
        # Calculate summary stats
        total_iscsi = len(iscsi_vols)
        total_nas = len(nas_vols)
        
        # Status analysis
        iscsi_healthy = sum(1 for v in iscsi_vols if v.get('Status') == 'OK')
        nas_healthy = sum(1 for v in nas_vols if v.get('Status') == 'OK')
        
        response = {
            "feature": "Feature 13: StoneFusion Inventory",
            "summary": {
                "total_volumes": total_iscsi + total_nas,
                "iscsi_count": total_iscsi,
                "nas_count": total_nas,
                "overall_health_pct": round(((iscsi_healthy + nas_healthy) / max(1, total_iscsi + total_nas)) * 100, 1)
            },
            "iscsi_volumes": iscsi_vols,
            "nas_volumes": nas_vols
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error in get_stonefusion_inventory: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)

def get_stonefusion_volume_details(volume_name: str) -> str:
    """
    MCP Tool: Retrieves detailed status for a specific volume (iSCSI or NAS).
    """
    try:
        client = StoneFlyClient()
        
        # Try finding it in iSCSI first
        details = {}
        vol_type = "Unknown"
        
        try:
            details = client.get_iscsi_volume_details(volume_name)
            if details:
                vol_type = "iSCSI"
        except:
            pass
            
        # If not found, try NAS
        if not details:
            try:
                details = client.get_nas_volume_details(volume_name)
                if details:
                    vol_type = "NAS"
            except:
                pass
        
        if not details:
             return json.dumps({
                 "status": "NOT_FOUND",
                 "message": f"Volume '{volume_name}' not found in iSCSI or NAS lists."
             }, indent=2)

        response = {
            "feature": "Feature 13: Volume Details",
            "volume_name": volume_name,
            "type": vol_type,
            "details": details
        }
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.error(f"Error in get_stonefusion_volume_details: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)

if __name__ == "__main__":
    # Test run
    print("Testing StoneFly Client...")
    try:
        # result = get_stonefusion_events(limit=5)
        # print(result)
        pass 
    except Exception as e:
        print(f"Test failed: {e}")
