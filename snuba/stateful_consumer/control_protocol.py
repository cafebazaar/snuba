from __future__ import annotations

import jsonschema

from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from abc import ABC

from snuba.snapshots import SnapshotId
from snuba.snapshots.postgres_snapshot import Xid

CONTROL_MSG_SCHEMA = {
    'anyOf': [
        {"$ref": "#/definitions/snapshot-init"},
        {"$ref": "#/definitions/snapshot-abort"},
        {"$ref": "#/definitions/snapshot-loaded"},
    ],
    "definitions": {
        "base": {
            "type": "object",
            "properties": {
                "snapshot-id": {
                    "type": "string"
                }
            },
            "required": ["event", "snapshot-id"],
        },
        "snapshot-init": {
            "allOf": [
                {"$ref": "#/definitions/base"},
                {
                    "properties": {
                        "event": {"const": "snapshot-init"},
                        "product": {"type": "string"},
                    },
                    "required": ["event", "product"],
                }
            ]
        },
        "snapshot-abort": {
            "allOf": [
                {"$ref": "#/definitions/base"},
                {
                    "properties": {
                        "event": {"const": "snapshot-abort"},
                    },
                    "required": ["event"],
                }
            ]
        },
        "dataset": {
            "type": "object",
            "properties": {
                "temp_table": {"type": "string"},
            },
            "required": ["temp_table"],
        },
        "snapshot-loaded": {
            "allOf": [
                {"$ref": "#/definitions/base"},
                {
                    "properties": {
                        "event": {"const": "snapshot-loaded"},
                        "datasets": {
                            "type": "object",
                            "additionalProperties": {
                                '$ref': '#/definitions/dataset',
                            },
                        },
                        "transaction-info": {
                            "type": "object",
                            "properties": {
                                "xmin": {"type": "number"},
                                "xmax": {"type": "number"},
                                "xip-list": {
                                    "type": "array",
                                    "items": [
                                        {"type": "number"}
                                    ],
                                },
                            }
                        }
                    },
                    "required": ["event", "datasets", "transaction-info"],
                }
            ]
        }
    }
}


@dataclass(frozen=True)
class ControlMessage(ABC):
    id: SnapshotId

    @classmethod
    def from_json(cls, json: Mapping[str, Any]) -> ControlMessage:
        raise NotImplementedError


@dataclass(frozen=True)
class SnapshotInit(ControlMessage):
    product: str

    @classmethod
    def from_json(cls, json: Mapping[str, Any]) -> ControlMessage:
        assert json["event"] == "snapshot-init"
        return SnapshotInit(
            id=json["snapshot-id"],
            product=json["product"],
        )


@dataclass(frozen=True)
class SnapshotAbort(ControlMessage):

    @classmethod
    def from_json(cls, json: Mapping[str, Any]) -> ControlMessage:
        assert json["event"] == "snapshot-abort"
        return SnapshotAbort(
            id=json["snapshot-id"],
        )


DatasetMetadata = Mapping[str, Any]


@dataclass(frozen=True)
class TransactionData:
    """
    Provides the metadata for the loaded snapshot.
    """
    xmin: Xid
    xmax: Xid
    xip_list: Sequence[Xid]


@dataclass(frozen=True)
class SnapshotLoaded(ControlMessage):
    datasets: Mapping[str, DatasetMetadata]
    transaction_info: TransactionData

    @classmethod
    def from_json(cls, json: Mapping[str, Any]) -> ControlMessage:
        assert json["event"] == "snapshot-loaded"
        return SnapshotLoaded(
            id=json["snapshot-id"],
            datasets=json["datasets"],
            transaction_info=TransactionData(
                xmin=json["transaction-info"]["xmin"],
                xmax=json["transaction-info"]["xmax"],
                xip_list=json["transaction-info"]["xip-list"],
            )
        )


def parse_control_message(message: Mapping[str, Any]) -> ControlMessage:
    jsonschema.validate(message, CONTROL_MSG_SCHEMA)
    event_type = message["event"]
    if event_type == "snapshot-init":
        return SnapshotInit.from_json(message)
    elif event_type == "snapshot-abort":
        return SnapshotAbort.from_json(message)
    elif event_type == "snapshot-loaded":
        return SnapshotLoaded.from_json(message)
    else:
        raise ValueError(f"Invalid control message with event type: {event_type}")