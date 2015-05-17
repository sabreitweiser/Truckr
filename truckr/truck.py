class Truck:
	'''
	Class to represent a food truck. Currently stores name, address, food
	list, latitude, and longitude. May be expanded to take more information.
	'''
	def __init__(self):
		self.name = ""
		self.address = ""
		self.food = []
		self.lat = 0.0
		self.lon = 0.0
	def __str__(self):
		return self.name+": "+self.address
