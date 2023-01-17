from pathlib import Path
from zipfile import ZipFile, ZipInfo, is_zipfile
from typing import Any, cast, List
import re
import yaml
from tempfile import TemporaryDirectory
from jsonpointer import JsonPointer


class InvalidCodeQLDatabase(Exception):
    pass


class CodeQLDatabase:
    def __init__(self, database: Path) -> None:
        if not database.exists():
            raise InvalidCodeQLDatabase("Database does not exists!")

        if database.is_dir():
            db_metadata = database / "codeql-database.yml"
            if db_metadata.exists():
                with db_metadata.open() as fd:
                    database_info = yaml.safe_load(fd)
            else:
                raise InvalidCodeQLDatabase(
                    "Invalid database, missing 'codeql-database.yml'!"
                )
        elif is_zipfile(database):
            with ZipFile(database) as fd:

                def is_db_metadata(zi: ZipInfo) -> bool:
                    path_parts = zi.filename.split("/")
                    return (
                        len(path_parts) == 2 and path_parts[1] == "codeql-database.yml"
                    )

                db_metadata_candidates = list(filter(is_db_metadata, fd.infolist()))
                if len(db_metadata_candidates) == 0:
                    raise InvalidCodeQLDatabase(
                        "Invalid database, missing 'codeql-database.yml'!"
                    )
                elif len(db_metadata_candidates) > 1:
                    raise InvalidCodeQLDatabase(
                        "Invalid database, found multiple 'codeql-database.yml'!"
                    )
                else:
                    self.db_metadata_filename = db_metadata_candidates[0].filename
                    database_info = yaml.safe_load(fd.read(self.db_metadata_filename))

        else:
            raise InvalidCodeQLDatabase(
                "Expected a database directory or database zip archive!"
            )

        self.database_info = database_info
        self.database = database

    def set_property(self, **kwargs: Any) -> None:
        for key in kwargs.keys():
            if key in self.database_info:
                raise KeyError(f"Property with key {key} is immutable!")

        def update_or_set_props(database: Path, **kwargs: Any):
            user_properties = database / "user-properties.yml"
            props = kwargs
            if user_properties.exists():
                with user_properties.open("r") as fd:
                    existing_props = yaml.safe_load(fd)
                    if existing_props and not isinstance(existing_props, dict):
                        raise InvalidCodeQLDatabase(
                            "The 'user-properties.yml' is not a YAML dictionary!"
                        )
                    else:
                        props = existing_props | props
            with user_properties.open("w") as fd:
                fd.write(yaml.dump(props))

        if self.database.is_dir():
            update_or_set_props(self.database, **kwargs)
        else:
            with TemporaryDirectory() as tmp_dir:
                with ZipFile(str(self.database), mode="r") as fd:
                    fd.extractall(tmp_dir)
                database = Path(tmp_dir) / self.db_metadata_filename.split("/")[0]
                update_or_set_props(database, **kwargs)
                with ZipFile(self.database, mode="w") as fd:
                    for f in database.glob("**/*"):
                        fd.write(str(f), arcname=str(f.relative_to(tmp_dir)))

    def __translate_key(self, key: str) -> JsonPointer:
        # Create a json pointer from key by replacing '.' with '/' and array accesses with json pointer syntax.
        # Example: "foo.bar[0].baz" -> "/foo/bar/0/baz"
        path = re.sub(r"\[(\d+)\]", r"/\1", key.replace(".", "/"))
        if not path.startswith("/"):
            path = "/" + path
        return JsonPointer(path)

    def get_property(self, key: str) -> Any:

        database_property = self.__translate_key(key).get(
            self.database_info, default=None
        )
        if database_property is not None:
            return database_property

        user_properties = None
        if self.database.is_dir():
            user_properties_path = self.database / "user-properties.yml"
            if user_properties_path.exists():
                with user_properties_path.open() as fd:
                    user_properties = yaml.safe_load(fd)
        else:

            def is_user_property_file(zi: ZipInfo) -> bool:
                return zi.filename.endswith("user-properties.yml")

            with ZipFile(str(self.database)) as fd:
                user_property_candidates = list(
                    filter(is_user_property_file, fd.infolist())
                )
                if len(user_property_candidates) == 0:
                    raise InvalidCodeQLDatabase("Found no 'user-properties.yml' files!")
                if len(user_property_candidates) > 1:
                    raise InvalidCodeQLDatabase(
                        "Found multiple 'user-properties.yml' files!"
                    )
                user_properties = yaml.safe_load(fd.read(user_property_candidates[0]))
        return self.__translate_key(key).get(user_properties, default=None)
