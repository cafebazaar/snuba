from snuba.datasets.factory import get_dataset, get_dataset_name
from tests.base import BaseTest


class TestGetDatasetName(BaseTest):
    def test(self):
        dataset_name = "events"
        assert get_dataset_name(get_dataset(dataset_name)) == dataset_name
