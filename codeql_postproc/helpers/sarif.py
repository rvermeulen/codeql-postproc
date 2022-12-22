import json
from pathlib import Path
from typing import List, Any, cast, Dict
import jsonschema
import jsonschema.exceptions

class InvalidSarif(Exception):
    pass

class Sarif:
    def __init__(self, path: Path) -> None:
        self.path = path

        schema_path = Path(__file__).parent.parent / "schemas" / "sarif-schema-2.1.0.json"
        self.schema = json.loads(schema_path.read_text())
      
        try:
            self.content: Dict[str, Any] = json.loads(self.path.read_text())
            jsonschema.validate(self.content, self.schema)
        except json.decoder.JSONDecodeError:
            raise InvalidSarif("Invalid JSON file!")

    def add_version_control_provenance(self, repository_url: str, revision_id: str, branch: str) -> None:
        if not "runs" in self.content or len(self.content["runs"]) == 0:
            raise InvalidSarif("Missing or no run objects in 'runs' property!")

        for run in self.content["runs"]:
            if "versionControlProvenance" in run:
                vcp: Any = run["versionControlProvenance"]
                if not isinstance(vcp, list):
                    raise InvalidSarif("The 'versionControlProvenance' property is not an array!")
            else:
                run["versionControlProvenance"] = []
        
            cast(List[Dict[str, str]], run["versionControlProvenance"]).append({
                "repositoryUri": repository_url,
                "revisionId": revision_id,
                "branch": branch
            })

        try:
            jsonschema.validate(self.content, self.schema)
        except jsonschema.exceptions.ValidationError as e:
            raise InvalidSarif(f"Adding the version control provenance information results in an invalid Sarif file because {e.message}!")
        with self.path.open(mode="w") as fd:
            json.dump(self.content, fd, indent=2)

