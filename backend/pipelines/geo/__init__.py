"""Pan-India geography lane: city registry, zone tessellation, national rollup.

This lane turns NeerDrishti from a one-city demo into national coverage. Everything
downstream (satellite, billing, groundwater, fusion) is already per-`zone_id`, so
widening the country is a geography problem, not an architecture problem.
"""
