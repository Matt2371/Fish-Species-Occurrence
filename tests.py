import pytest

import species_stream_order
import support


def test_max_stream_order_by_huc():
	max_stream_order_fc = species_stream_order.get_max_stream_order_by_huc()
	max_stream_orders = support.get_attribute_dict(max_stream_order_fc, "HUC_12", "MAX_StreamOrde")

