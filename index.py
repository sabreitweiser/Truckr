from truckr import load_trucks, get_trucks
from redis import StrictRedis
from urlparse import parse_qsl
from json import dumps
def app(environ, start_response):
	ret = {}
	qs = dict(parse_qsl(environ["QUERY_STRING"]))
	red = StrictRedis(host="localhost", port=6379, db=0)
	root_key = red.get("root")
	if root_key is None: #Load trucks into redis if there is no tree already in it
		inp_file = "Mobile_Food_Facility_Permit.csv"
		load_trucks(inp_file, red)
		root_key = red.get("root")
	try:
		lat = float(qs["latitude"])
		lon = float(qs["longitude"])
		rad = float(qs["radius"])
	except KeyError: #Return error if required fields aren't present
		start_response("400 Bad Request", [("Content-type", "text/plain")])
		ret["error"] = "latitude, longitude, and radius query parameters are required"
		return [dumps(ret)]
	ret["latitude"] = lat
	ret["longitude"] = lon
	ret["radius"] = rad
	food = qs.get("food", "").upper()
	if food:
		ret["food"] = food
		ret["trucks"] = [str(t)
				for t in get_trucks(lat, lon, rad, red, root_key) if food in t.food]
	else:
		trucks = []
		foods = set()
		for t in get_trucks(lat, lon, rad, red, root_key):
			trucks.append(str(t))
			foods |= set(t.food)
		ret["trucks"] = trucks
		ret["foods"] = list(foods)
	start_response("200 OK", [("Content-type", "text/plain")])
	return [dumps(ret)]
