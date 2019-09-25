import arcpy


def get_attribute_dict(feature_class, key, attribute, where_clause=None):
	"""
		Makes a dictionary of an attribute in a feature class. This is to support testing so we can
		grab the max stream order for a HUC and check that it's the correct value.
	:param feature_class:
	:param key:
	:param attribute:
	:return:
	"""
	cursor = arcpy.da.SearchCursor(feature_class, [key, attribute], where_clause=where_clause)

	output_dict = {}

	for row in cursor:
		output_dict[row[0]] = row[1]

	return output_dict