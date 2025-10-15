"""Lambda de rotação de segredo do RDS Postgres.

A função implementa o ciclo padrão de rotação do Secrets Manager:
createSecret -> setSecret -> testSecret -> finishSecret.

Ela gera uma nova senha, aplica diretamente na instância RDS e promove a
versão após validar que a instância está disponível novamente.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

_SECRETSMANAGER = boto3.client("secretsmanager")
_RDS = boto3.client("rds")

_DB_INSTANCE_IDENTIFIER = os.environ["DB_INSTANCE_IDENTIFIER"]
_PASSWORD_LENGTH = int(os.environ.get("PASSWORD_LENGTH", "32"))
_EXCLUDE_CHARACTERS = os.environ.get("EXCLUDE_CHARACTERS", '"\\/@')


class RotationError(RuntimeError):
    """Erro durante a rotação do segredo."""


@dataclass(frozen=True)
class SecretMetadata:
    arn: str
    token: str
    stages: dict[str, list[str]]


def lambda_handler(event: dict[str, Any], _: Any) -> None:
    LOGGER.debug("rotation_event", event=event)

    metadata = _describe_secret(event)
    stage = event["Step"]

    if stage == "createSecret":
        _create_secret(metadata)
    elif stage == "setSecret":
        _set_secret(metadata)
    elif stage == "testSecret":
        _test_secret(metadata)
    elif stage == "finishSecret":
        _finish_secret(metadata)
    else:  # pragma: no cover - defesa
        raise RotationError(f"Etapa de rotação desconhecida: {stage}")


def _describe_secret(event: dict[str, Any]) -> SecretMetadata:
    arn = event["SecretId"]
    token = event["ClientRequestToken"]

    try:
        response = _SECRETSMANAGER.describe_secret(SecretId=arn)
    except ClientError as exc:  # pragma: no cover - erro de infraestrutura
        raise RotationError(f"Não foi possível descrever o segredo {arn}: {exc}") from exc

    version_map = response.get("VersionIdsToStages", {})
    if token not in version_map:
        raise RotationError("Versão informada não está registrada no segredo")

    return SecretMetadata(arn=arn, token=token, stages=version_map)


def _create_secret(metadata: SecretMetadata) -> None:
    stages = metadata.stages.get(metadata.token, [])
    if "AWSPENDING" in stages:
        LOGGER.info("createSecret já executado para esta versão", token=metadata.token)
        return

    LOGGER.info("Gerando nova senha temporária", token=metadata.token)
    current_secret = _get_secret_dict(metadata.arn, version_stage="AWSCURRENT")

    new_password = _SECRETSMANAGER.get_random_password(
        PasswordLength=_PASSWORD_LENGTH,
        ExcludeCharacters=_EXCLUDE_CHARACTERS,
        RequireEachIncludedType=True,
    )["RandomPassword"]

    pending_secret = dict(current_secret)
    pending_secret["password"] = new_password

    _SECRETSMANAGER.put_secret_value(
        SecretId=metadata.arn,
        ClientRequestToken=metadata.token,
        SecretString=json.dumps(pending_secret),
        VersionStages=["AWSPENDING"],
    )


def _set_secret(metadata: SecretMetadata) -> None:
    pending_secret = _get_secret_dict(metadata.arn, version_id=metadata.token)
    password = pending_secret.get("password")
    if not password:
        raise RotationError("Versão pendente não contém senha")

    LOGGER.info("Aplicando nova senha no RDS", db_instance=_DB_INSTANCE_IDENTIFIER)
    try:
        _RDS.modify_db_instance(
            DBInstanceIdentifier=_DB_INSTANCE_IDENTIFIER,
            MasterUserPassword=password,
            ApplyImmediately=True,
        )
        waiter = _RDS.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=_DB_INSTANCE_IDENTIFIER)
    except ClientError as exc:
        raise RotationError(f"Falha ao aplicar senha no RDS: {exc}") from exc


def _test_secret(metadata: SecretMetadata) -> None:
    LOGGER.info("Validando estado do RDS após alteração de senha")
    try:
        response = _RDS.describe_db_instances(DBInstanceIdentifier=_DB_INSTANCE_IDENTIFIER)
    except ClientError as exc:
        raise RotationError(f"Falha ao consultar instância RDS: {exc}") from exc

    status = response["DBInstances"][0]["DBInstanceStatus"]
    if status != "available":
        raise RotationError(f"Instância RDS ainda não está disponível (status={status})")


def _finish_secret(metadata: SecretMetadata) -> None:
    current_version = _find_version_with_stage(metadata.stages, "AWSCURRENT")
    if current_version == metadata.token:
        LOGGER.info("Versão pendente já é a atual", token=metadata.token)
        return

    LOGGER.info("Promovendo nova versão do segredo", token=metadata.token)
    _SECRETSMANAGER.update_secret_version_stage(
        SecretId=metadata.arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=metadata.token,
        RemoveFromVersionId=current_version,
    )


def _get_secret_dict(arn: str, *, version_stage: str | None = None, version_id: str | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"SecretId": arn}
    if version_stage:
        kwargs["VersionStage"] = version_stage
    if version_id:
        kwargs["VersionId"] = version_id

    try:
        response = _SECRETSMANAGER.get_secret_value(**kwargs)
    except ClientError as exc:
        raise RotationError(f"Não foi possível recuperar o segredo {arn}: {exc}") from exc

    if "SecretString" not in response:
        raise RotationError("Segredo não contém SecretString")

    return json.loads(response["SecretString"])


def _find_version_with_stage(version_map: dict[str, list[str]], stage: str) -> str | None:
    for version, stages in version_map.items():
        if stage in stages:
            return version
    return None
