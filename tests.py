import pytest

import species_stream_order
import support

flowlines = r"C:\Users\dsx\Code\belleflopt\data\NHDPlusV2\NHDPlusV2.gdb\NHDFlowline_Network"
huc12s = r"C:\Users\dsx\Code\PISCES\data\PISCES_map_data.gdb\HUC12FullState"


def test_max_stream_order_by_huc():
	max_stream_order_fc = species_stream_order.get_max_stream_order_by_huc(nhd_flowline=flowlines, huc12s=huc12s)

	where_clause = "HUC_12 in ('180201250701', '180201250702','180201250703','180201250704','180201251002')"
	max_stream_orders = support.get_attribute_dict(max_stream_order_fc, "HUC_12", "MAX_StreamOrde", where_clause=where_clause)

	# manually collected max stream orders by Nick on 9/24/2019
	assert max_stream_orders["180201250701"] == 3
	assert max_stream_orders["180201250702"] == 4
	assert max_stream_orders["180201250703"] == 4
	assert max_stream_orders["180201250704"] == 4
	assert max_stream_orders["180201251002"] == 5
