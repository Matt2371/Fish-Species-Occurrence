import arcpy


def get_attribute_dict(feature_class, key, attribute):
	"""
		Makes a dictionary of an attribute in a feature class. This is to support testing so we can
		grab the max stream order for a HUC and check that it's the correct value.
	:param feature_class:
	:param key:
	:param attribute:
	:return:
	"""
	cursor = arcpy.SearchCursor(feature_class)

	output_dict = {}

	for row in cursor:
		output_dict[row.getValue(key)] = row.getValue(attribute)

	return output_dict