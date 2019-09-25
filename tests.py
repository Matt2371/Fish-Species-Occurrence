import pytest

import species_stream_order
import support

def test_max_stream_order_by_huc(flowlines=species_stream_order.FLOWLINES, huc12s=species_stream_order.HUC12S):
	max_stream_order_fc = species_stream_order.get_max_stream_order_by_huc(nhd_flowline=flowlines, huc12s=huc12s)

	# where clause seemed slow - maybe because of a lack of an index. Let's just pull it all in
	#where_clause = "HUC_12 in ('180201250701', '180201250702','180201250703','180201250704','180201251002')"
	max_stream_orders = support.get_attribute_dict(max_stream_order_fc, "HUC_12", "MAX_StreamOrde", where_clause=None)

	# manually collected max stream orders by Nick on 9/24/2019
	assert max_stream_orders["180201250701"] == 3
	assert max_stream_orders["180201250702"] == 4
	assert max_stream_orders["180201250703"] == 4
	assert max_stream_orders["180201250704"] == 4
	assert max_stream_orders["180201251002"] == 5

	assert max_stream_orders["180201630703"] == 7  # outlet to suisun bay from the central valley
