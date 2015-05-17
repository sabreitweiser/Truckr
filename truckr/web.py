from truck import Truck
from pyrtree import RTree, Rect
from math import pi, cos
from geopy.distance import vincenty
from collections import Counter
try:
	from cPickle import dumps, loads, HIGHEST_PROTOCL
except ImportError:
	from pickle import dumps, loads, HIGHEST_PROTOCOL
def ser(obj):
	'''
	Serialize an object for use in Redis, abstraction
	'''
	return dumps(obj, HIGHEST_PROTOCOL)
def deser(obj):
	'''
	Deserialize an object returned from Redis, abstraction
	'''
	return loads(obj)

def _get_trucks_from_file(inp_file):
	'''
	Internal function to get trucks from a csv.
	Takes input file path, yields assembled Truck objects
	'''
	with open(inp_file, 'r') as inp:
		first_line = True
		for line in inp:
			items = line.strip().split(",")
			if first_line:
				name_idx = items.index("Applicant")
				address_idx = items.index("Address")
				food_idx = items.index("FoodItems")
				status_idx = items.index("Status")
				lat_idx = items.index("Latitude")
				lon_idx = items.index("Longitude")
				first_line = False
				continue
			status = items[status_idx]
			if status != "APPROVED": #Don't want expried/requested trucks
				continue
			t = Truck()
			try: #Some trucks don't have latlong; could GeoCode from address, but that's another project
				t.lat = float(items[lat_idx])
				t.lon = float(items[lon_idx])
			except ValueError:
				continue
			t.name = items[name_idx]
			t.address = items[address_idx]
			t.food = [f.strip().upper() for f in items[food_idx].split(":")]
			yield t

TRUCK_SIZE = 0.0001 #In degrees, on the order of 10 meters. For RTree insertion
def _load_trucks_into_tree(inp_file):
	'''
	Internal function to load trucks, given in inp_file csv, into an RTree.
	Takes input file as path argument, return RTree.
	'''
	tree = RTree()
	for t in _get_trucks_from_file(inp_file):
		tree.insert(t, Rect(t.lat-TRUCK_SIZE, t.lon-TRUCK_SIZE,
					t.lat+TRUCK_SIZE, t.lon+TRUCK_SIZE))
	return tree

def _load_tree_into_redis(tree, red):
	'''
	Internal function to load truck Rtree into redis.
	Takes loaded tree and setup redis instance as arguments.
	'''
	p = lambda a,b: True
	with red.pipeline() as pipe:
		first = True
		for r in tree.walk(p):
			if first:
				pipe.set("root", ser(r.rect))
				first = False
			if not r.is_leaf():
				value = [[], []]
				for rr in r.children():
					if rr.is_leaf():
						value[1].append(rr.leaf_obj())
					else:
						value[0].append(rr.rect)
				pipe.set(ser(r.rect), ser(value))
		pipe.execute()
def load_trucks(input_file, redis_instance):
	'''
	Function to load food truck data from a CSV file (such as the one exported from
	https://data.sfgov.org/Economy-and-Community/Mobile-Food-Facility-Permit/rqzj-sfat?
	) and load all active (APPROVED) trucks into an R-tree. The R-tree is then dumped into
	the given Redis instance for use in a get_foods call. Usage is:
	load_trucks(input_file, redis_instance)
	'''
	tree = _load_trucks_into_tree(input_file)
	_load_tree_into_redis(tree, redis_instance)

def _get_trucks_in_rect(bound_rect, node, red):
	'''
	Internal function to get all trucks in a bounding rectangle. Recurses through RTree in
	Redis to find all trucks within bound_rect.
	'''
	if node[0]:
		next_nodes = []
		with red.pipeline() as pipe:
			for r in node[0]:
				if not r.does_intersect(bound_rect):
					continue
				pipe.get(ser(r))
			next_nodes = [deser(rr) for rr in pipe.execute()]
		for n in next_nodes:
			for t in _get_trucks_in_rect(bound_rect, n, red):
				yield t
	if node[1]:
		for t in node[1]:
			if bound_rect.does_containpoint((t.lat, t.lon)):
				yield t
EARTH_RADIUS = 24901.0 #In miles
def _get_bound_rect(lat, lon, radius):
	'''
	Internal function to get bounding rectangle around radius around lat/lon coords.
	'''
	#TODO: Is this formula correct?
	#TODO: Update for spherical considerations if expanding beyond SF
	dlat = (radius/EARTH_RADIUS)*360 #latitude always subtends constant arclength
	#Want to get longitude subtended at most extreme latitude, since that will be most variable
	if abs(lat+dlat) < abs(lat-dlat):
		dlon = (radius/(EARTH_RADIUS*cos((lat+dlat)*pi/180)))*360
	else:
		dlon = (radius/(EARTH_RADIUS*cos((lat-dlat)*pi/180)))*360
	return Rect(lat-dlat, lon-dlon, lat+dlat, lon+dlon)

def get_trucks(lat, lon, radius, red, root_key = None):
	'''
	Gets foods available at trucks within a radius (in miles) of a latitude/longitude point.
	Uses truck data from a give redis instance, with tree starting at root_key. Usage is:
	get_foods(latitude, longitude, radius, redis_instance, root_key)
	'''
	if root_key is None:
		root_key = red.get("root")
	bound_rect = _get_bound_rect(lat, lon, radius)
	node = deser(red.get(root_key))
	foods = Counter()
	for t in _get_trucks_in_rect(bound_rect, node, red):
		if vincenty((lat,lon), (t.lat, t.lon)).miles < radius:
			yield t
#Test
def load_trucks_seq(input_file, redis_instance):
	'''
	Naive method to load every truck into one Redis key, for testing purposes.
	Mimics load_trucks signature.
	'''
	with redis_instance.pipeline() as pipe:
		pipe.delete("trucks")
		for t in _get_trucks_from_file(input_file):
			pipe.lpush("trucks", ser(t))
		pipe.execute()

def get_trucks_seq(lat, lon, radius, red, truck_key = "trucks"):
	'''
	Naive method that checks every truck, for testing purposes.
	Mimics get_trucks signature.
	'''
	foods = Counter()
	L = red.llen(truck_key)
	ts = red.lrange(truck_key, 0, L)
	for _t in ts:
		t = deser(_t)
		if vincenty((lat,lon), (t.lat, t.lon)).miles < radius:
			yield t
#/Test
