import click
from pathlib import Path
from sys import exit
from typing import Optional, cast

@click.group()
def cli() -> None:
    pass

@cli.group()
def database() -> None:
    pass

@database.command("add-vcs-provenance")
@click.option("-u", "--repository-uri", required=True, help="An absolute URI that specifies the location of the repository.")
@click.option("-r", "--revision-id", required=True, help="A string that uniquely and permanently identifies the revision.")
@click.argument("database", type=click.Path(exists=True, path_type=Path), required=True)
def database_add_provenance(repository_uri: str, revision_id: str, database: Path) -> None:
    from codeql_postproc.helpers.codeql import CodeQLDatabase, InvalidCodeQLDatabase

    try:
        codeql_db = CodeQLDatabase(database)
        vcs_provenance = [{
            'repositoryUri': repository_uri,
            'revisionId': revision_id
        }]
        codeql_db.set_property(versionControlProvenance=vcs_provenance)
    except InvalidCodeQLDatabase as e:
        click.echo(e, err=True)
        exit(1)

@database.command("get-property")
@click.option("-f", "--format", "output_format", type=click.Choice(["json", "yaml"]), default="yaml")
@click.argument("key", required=True)
@click.argument("database", type=click.Path(exists=True, path_type=Path), required=True)
def get_property(output_format: str, key: str, database: Path) -> None:
    from codeql_postproc.helpers.codeql import CodeQLDatabase, InvalidCodeQLDatabase
    import yaml
    import json
    import sys

    try:
        codeql_db = CodeQLDatabase(database)
        value = codeql_db.get_property(key)
        if output_format == "yaml": 
            yaml.dump(value, sys.stdout)
        elif output_format == "json":
            json.dump(value, sys.stdout)
        else:
            click.echo(f"Unimplemented output format {output_format}!")
            exit(1)
    except KeyError:
        click.echo(f"The database does not have a property with key {key}.", err=True)
        exit(1)
    except InvalidCodeQLDatabase as e:
        click.echo(e, err=True)
        exit(1)

@cli.group("sarif")
def sarif() -> None:
    pass

@sarif.command("add-vcs-provenance")
@click.option("-d", "--from-database", is_flag=True)
@click.option("-u", "--repository-uri", help="An absolute URI that specifies the location of the repository.")
@click.option("-r", "--revision-id", help="A string that uniquely and permanently identifies the revision.")
@click.argument("sarif_path", type=click.Path(exists=True, path_type=Path, dir_okay=False), required=True)
@click.argument("database_path", type=click.Path(exists=True, path_type=Path), required=False)
def sarif_add_provenance(from_database: bool, repository_uri: str, revision_id: str, sarif_path: Path, database_path: Optional[Path]) -> None:
    from codeql_postproc.helpers.codeql import CodeQLDatabase, InvalidCodeQLDatabase
    from codeql_postproc.helpers.sarif import Sarif, InvalidSarif

    if from_database and not database_path:
        raise click.BadArgumentUsage("A database must be specified when using the --from-database option!")
    
    if not from_database and not repository_uri:
        raise click.BadOptionUsage("--repository-uri", "The option '--repository-uri' must be specified if not importing from a database!")
    if not from_database and not revision_id:
        raise click.BadOptionUsage("--revision-id", "The option '--revision-id' must be specified if not importing from a database!")

    if from_database:
        try:
            codeql_db = CodeQLDatabase(cast(Path, database_path))
            # Assume there is only one array element for now.
            vcp = codeql_db.get_property("versionControlProvenance")[0]
            if not "repositoryUri" in vcp:
                click.echo(f"The database's version control provenance misses the 'repositoryUri' property!", err=True)
                exit(1)
            repository_uri = vcp["repositoryUri"]
            if not "revisionId" in vcp:
                click.echo(f"The database's version control provenance misses the 'revisionId' property!", err=True)
                exit(1)
            revision_id = vcp["revisionId"]
        except KeyError:
            click.echo(f"The database does not have any version control provenance property.", err=True)
            exit(1)
        except InvalidCodeQLDatabase as e:
            click.echo(e, err=True)
            exit(1)

    try:
        sarif = Sarif(sarif_path)
        sarif.add_version_control_provenance(repository_uri, revision_id)
    except InvalidSarif as e:
        click.echo(f"Unable to process invalid Sarif file with reason: {e}")
        exit(1)

   
        
if __name__ == "__main__":
    cli()