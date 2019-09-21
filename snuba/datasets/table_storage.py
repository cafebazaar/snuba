import json
import rapidjson

from datetime import datetime

from snuba.clickhouse import DATETIME_FORMAT
from snuba.datasets.schemas.tables import WritableTableSchema
from snuba.processor import MessageProcessor
from snuba.snapshots.bulk_load import BulkLoader
from snuba.writer import BatchWriter


class KafkaStreamLoader:
    """
    This class is a stream loader for a TableWriter. It provides what we need
    to start a Kafka consumer to fill in the table.
    """

    def __init__(
        self,
        processor: MessageProcessor,
        default_topic: str,
    ) -> None:
        self.__processor = processor
        self.__default_topic = default_topic

    def get_processor(self) -> MessageProcessor:
        return self.__processor

    def get_default_topic(self) -> str:
        return self.__default_topic

    def get_default_replication_factor(self):
        return 1

    def get_default_partitions(self):
        return 1


class TableWriter:
    """
    This class provides to a dataset write support on a Clickhouse table.
    It is schema aware (the Clickhouse write schema), it provides a writer
    to write on Clickhouse and a two loaders: one for bulk load of the table
    and the other for streaming load.

    Eventually, after some heavier refactoring of the consumer scripts,
    we could make the writing process more abstract and hide in this class
    the streaming, processing and writing. The writer in such architecture
    could coordinate the injestion process but that requires a reshuffle
    of responsibilities in the consumer scripts and a common interface
    between bulk load and stream load.
    """

    def __init__(self,
        write_schema: WritableTableSchema,
        stream_loader: KafkaStreamLoader,
    ) -> None:
        self.__table_schema = write_schema
        self.__stream_loader = stream_loader

    def get_write_schema(self) -> WritableTableSchema:
        return self.__table_schema

    def get_writer(self, options=None, table_name=None) -> BatchWriter:
        from snuba import settings
        from snuba.clickhouse.http import HTTPBatchWriter

        def default(value):
            if isinstance(value, datetime):
                return value.strftime(DATETIME_FORMAT)
            else:
                raise TypeError

        return HTTPBatchWriter(
            self.__table_schema,
            settings.CLICKHOUSE_HOST,
            settings.CLICKHOUSE_HTTP_PORT,
            lambda row: json.dumps(row, default=default).encode("utf-8"),
            options,
            table_name,
        )

    def get_bulk_writer(self, options=None, table_name=None) -> BatchWriter:
        """
        This is a stripped down verison of the writer designed
        for better performance when loading data in bulk.
        """
        # TODO: Consider using rapidjson to encode everywhere
        # once we will be confident it is reliable enough.

        from snuba import settings
        from snuba.clickhouse.http import HTTPBatchWriter

        return HTTPBatchWriter(
            self.__table_schema,
            settings.CLICKHOUSE_HOST,
            settings.CLICKHOUSE_HTTP_PORT,
            lambda row: rapidjson.dumps(row).encode("utf-8"),
            options,
            table_name,
            chunk_size=settings.BULK_CLICKHOUSE_BUFFER,
        )

    def get_bulk_loader(self, source, dest_table) -> BulkLoader:
        """
        Returns the instance of the bulk loader to populate the dataset from an
        external source when present.
        """
        raise NotImplementedError

    def get_stream_loader(self) -> KafkaStreamLoader:
        return self.__stream_loader
