# XMLTOMONGO

Quick script to import a SQL Server trace XML file to MongoDB for further analysis.

Yes I understand the irony of using MongoDB to review a SQL Server trace file, that's the fun part.

Once imported to mongodb you can quickly sort and review events



### Usage
`python3 ./main.py importfile.xml mongodbname mongodbcollectionname`

If `mongodbcollectionname` is found to already exist it will append a uuid to `mongodbcollectionname` and use that to avoid having multiple traces in one collection.

It should convert data to the matching MongoDB data types, like int and datetime.

I've tested this with exactly one XML trace file but I assume as MS has not updated SQL Server profiler in literally over a decade the format will be consistent enough.

### MongoDB Usage
Once you have the trace imported you can use a MongoDB client like robo3t to sort or see what else is going on in the trace;
```
db.trace.distinct("LoginName") //show every user that logged in

db.trace.sort({"StartTime":1}) //sort results by starttime, 1 means ascending, -1 descending

db.trace.find({"Duration":{$exists:true}}).sort({"Duration":-1}) //sort results by duration. Note that you have to filter by events that have a duration associated with them. Other wise the top results will be events without a duration

db.trace.find({"TextData":/arbitraryregex/}) //search TextData (aka the SQL statements executed) via regex

db.trace.find({"TextData": /arbitraryregex/}).forEach(function(i){print(i.TextData)}) //print out each sql query returned by the filter

```

The `forEach` ability detailed above is what makes mongodb so powerful and why I created the script. With this you can perform further analysis faster than with SQL.


### MongoDB Compatibility
The script uses the `pymongo` library to connect to MongoDB, this library has a limited set of versions supported;

PyMongo supports MongoDB 3.6, 4.0, 4.2, 4.4, 5.0, 6.0, and 7.0.

### MongoDB Authentication
As the `-m` option accepts mongodb connection strings you can use that for authentication;
```
python3 ./main.py import.xml sqltrace trace -m "mongodb://username:password@location:27017/?authSource=admin"
```