# Fish-Species-Occurrence
Transforms PISCES HUC12 level species occurrence data to NHD Stream Segment level.

## The problem
While California contains about 4,600 HUC12s, it contains ~130,000 NHD Stream Segments. The HUC12s are the coarsest
valid observation unit in PISCES, so this scale adjustment adds additional uncertainty to the species records. In order
to attach this additional uncertainty, the code here uses an approach based on strahler stream order and the species'
entire range to probabilistically assign species to segments within their broader range.

## The approach
In short, a species is assumed to be in all stream segments with a stream order equal to or greater than the minimum of
(maximum stream order in each HUC 12 in its range). To explain more clearly, we:
* Calculate the maximum stream order for any segment within each HUC 12.
* Using only the HUC12s representing a species' historical range, we find the minimum of those maximum values.

The assumption is that if we believe a species is in a given HUC12, in most cases, that means they're likely to be,
at least, in the outlet point of the HUC12 that connects the subwatershed to the rest of the range. This assumption
won't hold for highly endemic species (eg: Red Hills Roach), but is probably a reasonable approximation for most
wide-ranging species.
