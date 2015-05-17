import unittest
import os
from pyrtree import RTree, Rect
from fakeredis import FakeStrictRedis
from truckr.web import deser, load_trucks, get_trucks

class TestWeb(unittest.TestCase):
	def setUp(self):
		self.f = "test_trucks.csv"
		with open(self.f, "w") as out:
			out.write("Applicant,Address,FoodItems,Status,Latitude,Longitude")
			out.write("\n")
			out.write("MyTruck,1234 Main St,asdf:fdsa,APPROVED,37.0,-122.0")
		self.lat = 37.0
		self.lon = -122.0
		self.rad = 100.0
		self.name = "MyTruck"
		self.red = FakeStrictRedis()
		load_trucks(self.f, self.red)
	def tearDown(self):
		os.remove(self.f)
	def test_load_trucks(self):
		#Scan through all the keys, looking for leaf nodes with trucks
		for key in self.red.keys():
			if key == "root":
				continue #otherwise get type error
			trucks = deser(self.red.get(key))[1]
			if trucks: #If leaf node with truck list
				self.assertEqual(trucks[0].name, self.name)
				return
		self.assertTrue(False) #If no trucks found
	def test_get_trucks(self):
		for truck in get_trucks(self.lat, self.lon, self.rad,
				self.red, self.red.get("root")):
			self.assertEqual(truck.name, self.name)
			return
		self.assertTrue(False) #If no trucks found

if __name__ == '__main__':
	unittest.main()
