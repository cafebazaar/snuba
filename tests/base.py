import calendar
from hashlib import md5
from datetime import datetime, timedelta
import uuid
import six

from batching_kafka_consumer import AbstractBatchWorker, BatchingKafkaConsumer
from confluent_kafka import TopicPartition

from snuba import settings
from snuba.clickhouse import ClickhousePool
from snuba.redis import redis_client
from snuba.perf import FakeKafkaMessage
from snuba.writer import row_from_processed_event, write_rows


class FakeKafkaProducer(object):
    def __init__(self):
        self.messages = []
        self._callbacks = []

    def poll(self, *args, **kwargs):
        while self._callbacks:
            callback, message = self._callbacks.pop()
            callback(None, message)
        return 0

    def flush(self):
        return self.poll()

    def produce(self, topic, value, key=None, headers=None, on_delivery=None):
        message = FakeKafkaMessage(
            topic=topic,
            partition=None,  # XXX: the partition is unknown (depends on librdkafka)
            offset=None,  # XXX: the offset is unknown (depends on state)
            key=key,
            value=value,
            headers=headers,
        )
        self.messages.append(message)
        if on_delivery is not None:
            self._callbacks.append((on_delivery, message))


class FakeKafkaConsumer(object):
    def __init__(self):
        self.items = []
        self.commit_calls = 0
        self.close_calls = 0
        self.positions = {}

    def poll(self, *args, **kwargs):
        try:
            message = self.items.pop(0)
        except IndexError:
            return None

        self.positions[(message.topic(), message.partition())] = message.offset() + 1

        return message

    def commit(self, *args, **kwargs):
        self.commit_calls += 1
        return [
            TopicPartition(topic, partition, offset)
            for (topic, partition), offset in
            six.iteritems(self.positions)
        ]

    def close(self, *args, **kwargs):
        self.close_calls += 1


class FakeBatchingKafkaConsumer(BatchingKafkaConsumer):
    def create_consumer(self, *args, **kwargs):
        return FakeKafkaConsumer()


class FakeWorker(AbstractBatchWorker):
    def __init__(self, *args, **kwargs):
        super(FakeWorker, self).__init__(*args, **kwargs)
        self.processed = []
        self.flushed = []
        self.shutdown_calls = 0

    def process_message(self, message):
        self.processed.append(message.value())
        return message.value()

    def flush_batch(self, batch):
        self.flushed.append(batch)

    def shutdown(self):
        self.shutdown_calls += 1


class BaseTest(object):
    def setup_method(self, test_method):
        assert settings.TESTING, "settings.TESTING is False, try `SNUBA_SETTINGS=test` or `make test`"

        from fixtures import raw_event

        timestamp = datetime.utcnow()
        raw_event['datetime'] = (timestamp - timedelta(seconds=2)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        raw_event['received'] = int(calendar.timegm((timestamp - timedelta(seconds=1)).timetuple()))
        self.event = self.wrap_raw_event(raw_event)

        self.database = 'default'

        # TODO These tests are currently coupled pretty hard to the events dataset,
        # but eventually the base test should support multiple datasets.
        self.dataset = settings.get_dataset('events')
        self.clickhouse = ClickhousePool()

        self.clickhouse.execute(self.dataset.SCHEMA.get_local_table_drop())
        self.clickhouse.execute(self.dataset.SCHEMA.get_local_table_definition())
        redis_client.flushdb()

    def teardown_method(self, test_method):
        self.clickhouse.execute(self.dataset.SCHEMA.get_local_table_drop())
        redis_client.flushdb()

    def create_event_for_date(self, dt, retention_days=settings.DEFAULT_RETENTION_DAYS):
        """
        Creates a "processed" event, ie a flat dictionary that can directly be
        turned into a database row.
        """
        # TODO since this intermediate state is basically never seen by any code
        # as the processor.process_insert() returns a row now, perhaps we don't need
        # tests that rely on write_processed_events
        event = {
            'event_id': uuid.uuid4().hex,
            'project_id': 1,
            'group_id': 1,
            'deleted': 0,
        }
        event['timestamp'] = dt
        event['retention_days'] = retention_days
        return event

    def wrap_raw_event(self, event):
        """
        Wrap a raw event like the Sentry codebase does before sending to Kafka.
        """
        unique = "%s:%s" % (str(event['project']), event['id'])
        primary_hash = md5(unique.encode('utf-8')).hexdigest()

        return {
            'event_id': event['id'],
            'group_id': int(primary_hash[:16], 16),
            'primary_hash': primary_hash,
            'project_id': event['project'],
            'message': event['message'],
            'platform': event['platform'],
            'datetime': event['datetime'],
            'data': event
        }

    def write_raw_events(self, events):
        if not isinstance(events, (list, tuple)):
            events = [events]

        rows = []
        for event in events:
            if 'primary_hash' not in event:
                event = self.wrap_raw_event(event)

            rows.append(self.dataset.PROCESSOR.process_insert(event))

        write_rows(self.clickhouse, self.dataset, rows, types_check=True)

    def write_processed_events(self, events):
        if not isinstance(events, (list, tuple)):
            events = [events]

        rows = [row_from_processed_event(self.dataset.SCHEMA, event) for event in events]
        write_rows(self.clickhouse, self.dataset, rows, types_check=True)
