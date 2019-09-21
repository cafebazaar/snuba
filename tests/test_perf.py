from base import BaseEventsTest

from snuba.datasets.factory import get_dataset
from snuba import perf


class TestPerf(BaseEventsTest):
    def test(self):
        dataset = get_dataset('events')
        table = dataset.get_table_writer().get_write_schema().get_local_table_name()

        assert self.clickhouse.execute("SELECT COUNT() FROM %s" % table)[0][0] == 0

        perf.run('tests/perf-event.json', dataset)

        assert self.clickhouse.execute("SELECT COUNT() FROM %s" % table)[0][0] == 1
