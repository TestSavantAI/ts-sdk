import json
import requests

REMOTE_TS_API_ADDRESS = 'https://api.testsavant.ai'

REQUEST_JSON = """
{
    "prompt": "{PROMPT}",
    "config": {
        "project_id": "{PROJECT_ID}",
        "fail_fast": true,
        "cache": {
            "enabled": true,
            "ttl": 3600
        }
    },
    "use": [{SCANNERS}],
}
""".replace('\n', ' ')

class Scanner:
    
    def __init__(self, name, type, params={}):
        self.name = name
        self.type = type
        self.params = params
    
    def to_json(self):
        params = json.dumps(self.params)
        return f'{{"name": "{self.name}", "type": "{self.type}", "params": {params}}}'

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "params": self.params
        }

class TSGuard:
    
    def __init__(self, API_KEY, PROJECT_ID, remote_addr=REMOTE_TS_API_ADDRESS):
        self.API_KEY = API_KEY
        self.PROJECT_ID = PROJECT_ID
        self.scanners = []
        self.remote_addr = remote_addr
    
    def add_scanner(self, scanner):
        self.scanners.append(scanner)

    def _prepare_request_json(self, prompt, project_id, scanners, output = None):
        req_dict = {
            "prompt": prompt,
            "config": {
                "project_id": project_id,
                "fail_fast": True,
                "cache": {
                    "enabled": True,
                    "ttl": 3600
                }
            },
            "use": [scanner.to_dict() for scanner in scanners]
        }
        if output:
            req_dict["output"] = output
        return req_dict


class TSGuardInput(TSGuard):
    def __init__(self, API_KEY, PROJECT_ID, remote_addr=REMOTE_TS_API_ADDRESS):
        super().__init__(API_KEY, PROJECT_ID, remote_addr)
        self.remote_addr = remote_addr + "/guard/prompt"
        
    def scan(self, prompt):
        request_body = self._prepare_request_json(prompt, self.PROJECT_ID, self.scanners)
        response = requests.post(
            self.remote_addr,
            headers={
                'x-api-key': self.API_KEY,
                'Content-Type': 'application/json'
            },
            data=json.dumps(request_body)
        )
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}")
        return response.json()
    
class TSGuardOutput(TSGuard):
    def __init__(self, API_KEY, PROJECT_ID, remote_addr=REMOTE_TS_API_ADDRESS):
        super().__init__(API_KEY, PROJECT_ID, remote_addr)
        self.remote_addr = remote_addr + "/guard/output"
        
    def scan(self, prompt, output):
        request_body = self._prepare_request_json(prompt, self.PROJECT_ID, self.scanners, output=output)
        response = requests.post(
            self.remote_addr,
            headers={
                'x-api-key': self.API_KEY,
                'Content-Type': 'application/json'
            },
            data=json.dumps(request_body)
        )
        if response.status_code != 200:
            raise Exception(f"Request failed with status code {response.status_code}")
        return response.json()    
