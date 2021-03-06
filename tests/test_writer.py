import pytest
import rapidjson

from snuba.clickhouse.errors import ClickhouseWriterError
from snuba.clickhouse.http import HTTPBatchWriter
from snuba.datasets.factory import enforce_table_writer
from snuba.utils.metrics.backends.dummy import DummyMetricsBackend
from tests.backends.metrics import TestingMetricsBackend, Timing
from tests.base import BaseEventsTest


class TestHTTPBatchWriter(BaseEventsTest):
    def test_error_handling(self):
        table_writer = enforce_table_writer(self.dataset)
        metrics = DummyMetricsBackend(strict=True)

        with pytest.raises(ClickhouseWriterError) as error:
            table_writer.get_batch_writer(table_name="invalid", metrics=metrics).write(
                [rapidjson.dumps({"x": "y"}).encode("utf-8")]
            )

        assert error.value.code == 60

        with pytest.raises(ClickhouseWriterError) as error:
            table_writer.get_batch_writer(metrics=metrics).write(
                [b"{}", rapidjson.dumps({"timestamp": "invalid"}).encode("utf-8")]
            )

        assert error.value.code == 41
        assert error.value.row == 2

    @pytest.mark.parametrize(
        "chunk_size, input, expected_chunks",
        [
            (1, [b"a", b"b", b"c"], [b"a", b"b", b"c"],),
            (0, [b"a", b"b", b"c"], [b"abc"],),
            (2, [b"a", b"b", b"c"], [b"ab", b"c"],),
            (2, [b"a", b"b", b"c", b"d"], [b"ab", b"cd"],),
            (100000, [b"a", b"b", b"c"], [b"abc"],),
            (5, [], [],),
        ],
    )
    def test_chunks(self, chunk_size, input, expected_chunks):
        metrics = TestingMetricsBackend()

        table_name = "mysterious_inexistent_table"
        writer = HTTPBatchWriter(
            table_name=table_name,
            host="0:0:0:0",
            port=9000,
            user="default",
            password="",
            database="default",
            chunk_size=chunk_size,
            metrics=metrics,
        )

        chunks = writer._prepare_chunks(input)
        for chunk, expected in zip(chunks, expected_chunks):
            assert chunk == expected

        assert metrics.calls == [
            Timing("writer.chunk.size", len(chunk), {"table_name": table_name})
            for chunk in expected_chunks
        ] + [
            Timing(
                "writer.total.size",
                sum(map(len, expected_chunks)),
                {"table_name": table_name},
            )
        ]
