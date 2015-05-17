```
  ______                __       
 /_  __/______  _______/ /_______
  / / / ___/ / / / ___/ //_/ ___/
 / / / /  / /_/ / /__/ ,< / /    
/_/ /_/   \__,_/\___/_/|_/_/     
```
---------------------------------

Introduction
---------------------------------
Before we get into development details, let's see what Truckr can do! Truckr is built using Python 2, and since the app and all its dependencies (excluding Redis) are pure Python is can be run with any interpreter (CPython, Pypy, etc.). (Disclaimer: I've only tested it with CPython). First you'll need Redis, a key-value database used by Truckr. It should be available from your package manager of choice on most UNIX systems, for example:

$ apt-get install redis-server
(or)
$ brew install redis

Next, you'll need some python packages, which can be installed automatically by pip:
(optional) $ virtualenv truckr_env && source truckr_env/bin/activate
$ pip install -r requirements.txt

Optionally, you can run the automatic tests on your system to make sure everything is working:

$ python setup.py test

(NB: Installing the package isn’t necessary, since it can run fine in place.) Finally, you should start up redis and gunicorn (a python WSGI web-server than came with the requirements). Running Redis in the foreground, rather than as a background daemon, is recommended so that you can monitor it. You can do this by opening a new shell and running

$ redis-server

Back in your virtual environment shell, run the app on gunicorn (or any other WSGI server)

$ gunicorn index:app

Using curl, or your browser, you can now use the service. You'll need a latitude and longitude you want to search around, as well as a radius (in miles) to search, encoded as a GET query string. For example, you can get all trucks and foods available around Uber headquarters in a half mile radius with

$ curl -G -d "latitude=37.775267&longitude=-122.417636&radius=0.5" http://localhost:8000

Optionally, you can specify a particular food you want with the "food" parameter. For example, looking at the previous result I see “NACHOS” are available, so I try finding nachos in the same search area

$ curl -G -d "latitude=37.775267&longitude=-122.417636&radius=0.5&food=nachos" http://localhost:8000

The return is self-explanatory plaintext JSON.

---------------------------------

Development
---------------------------------
I’ve actually just recently built something similar to this, a python WSGI service that needed to keep persistent information. Our design pattern, which kept the python app stateless and used a local database (Redis) to store information, worked pretty well so I tried to make a similar architecture. I’m pretty comfortable with Python and Redis, but I’ve never built a RESTful API before, so I more-or-less winged the UI. Overall, it took me about 6 hours to develop Truckr, and another 6 hours to package, test, and document it.

The first thing I do with any project is look over the data itself. Looking over the data from DataSF, it was pretty complete. It included Names, addresses, latlong coordinates, and food lists; all I needed to make the service. The LocationDescription field seemed interesting, but didn't really give much more information than the address field, so I decided to leave it out in the first round (I could easily add back in later).

Some massaging would be nice; for example, there are a lot of trucks with multiple records that are probably just one truck with multiple possible locations. It would be ideal to collapse Anas Goodies Catering at 3305 3rd st with the one at 3255, and just present one truck with multiple locations. However, I couldn't see an easy way to do that, since, for example, the Anas Goodies catering at 640 Texas St was several miles away and probably shouldn't be grouped with those two. Similarly with the foods, it would be nice to group related foods, but that would also require significant word clustering. I decided that clustering of that level was beyond the scope of this project, and the only massaging I did was capitalize all of the foods (collapsing "Candy" and "candy", for example).

The biggest part of this project is clearly the storage and retrieval of Trucks near a certain point. Given that there are only a few hundred trucks, it would certainly be possible to just check them all; however, that wouldn't scale well to, say, all the trucks in the US. One option that came to mind was a multi-indexed SQL database, so that finding trucks in a bounding rectangle would just be a simple SELECT query, but I'm not very familiar with SQL. Instead, I went with an R-tree solution, a popular data structure for GIS/GPS systems that also gives a roughly logarithmic search time. Traversing an RTree is pretty easy, but building one is difficult, so I found an external library to build it for me. I could have used or built a wrapper around the popular libspatialindex R*-tree implementation, but I wanted to keep free from C/C++ dependencies. I found a good python package, pyrtree, that used k-means clustering to balance the tree and used that instead.

Once the tree is built from the data, I do some serialization and dump into redis, with each node a separate key. I don’t want to re-load the whole tree everytime, so I search through the tree in place in Redis, using some pipelining to speed things up. To search through the tree, I form a bounding rectangle around the search radius and get all of the trucks in that rectangle; then I filter out the trucks that aren’t really in the radius (using geopy’s distance algorithm). Once I’ve found all the trucks in the search radius, I filter out the ones without the food if a food query is specified. I then return the results as a plaintext JSON body.

---------------------------------

Testing
---------------------------------
Testing Truckr was a mixed bag; the automatic tests will easily catch big HALT_AND_CATCH_FIRE type errors, but testing for subtle correctness issues is difficult. The best thing I could do was test against a sequential version of the same framework, that checked every truck. The results were exactly the same for every query that I ran, so I was satisfied.

---------------------------------

Performance
---------------------------------
Performance is decent, returning in under 100ms on most queries of less than a mile radius on my system. The R-Tree as noticeably better than the sequential version that tested every truck; for example my test query for a half mile radius around Uber HQ ran in about half the time. Of course, your mileage may vary depending on the query and the app-Redis network performance.

---------------------------------

Documentation
---------------------------------
Most of the code is self-documented by doc-strings. The dir command will show you available symbols from the truckr modules, and the help command should bring up function signatures and doc-strings.

The most important parts of the package are the Truck class, the load_trucks function, and the get_trucks function.

The Truck class represents an individual Truck location, keeping track of name, address, lat(itude), lon(gitude), and food, and provides a string conversion that prints in “name: address” format.

The load_trucks function takes an input file path to a CSV file similar to the one exported by DataSF, as well as a Redis instance, and loads an RTree of trucks from the CSV into the Redis instance.

The get_trucks function takes a latitude, longitude, radius, and a Redis instance, and yields all trucks in that radius from the RTree in the redis instance. It also optionally takes a root_key parameter that gives the key pointing to the root of the RTree, giving a slight optimization in case you want to string it together with automated loading.

The “index.py” app gives an example of how to use the package. It forms a simple API that takes GET requests and returns JSON that includes trucks and foods available in the specified area. It will also filter trucks to return those that have a specific food if one is given.

---------------------------------

Possible Upgrades
---------------------------------
The most obvious upgrade would be a nice front-end UI. More error checking, as well as a nice Google Maps or umap integration would make it human-useable. It could also use some more filtering options beyond just food.

It would be pretty easy to support more advanced location queries, e.g. “Find me the nearest x trucks” or “Find me trucks in a polygon”, using the RTree. It would also be easy to expand Truck entries to keep track of things like schedules (available online) and ratings. Then we could run more complex queries, like “Find me the nearest 5 highly rated trucks that are open now and serve Nachos”.

More ambitiously, like I talked about in “Development”, combining trucks with multiple locations into one and clustering foods into categories would also help with usability.

Finally, I think there’s pretty good potential for allowing queries based on walking/driving/bicycling time rather than just radius. We could simply set a max radius (walking_speed * max_time), get all the trucks in that radius, and then query something like the Google Directions API to find which ones are actually within that walking distance.
