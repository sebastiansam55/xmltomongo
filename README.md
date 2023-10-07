# XML to MongoDB Importer

This script provides a utility to convert XML data into MongoDB documents, particularly designed to handle XML traces from SQL Server and Procmon.

**Yes, I understand the irony of using MongoDB to review a SQL Server trace file. That's the fun part!**

By importing trace data into MongoDB, you can leverage MongoDB's powerful querying capabilities to quickly sort, filter, and review events. This especially comes in handy when dealing with extensive trace data where MongoDB offers a more efficient way to analyze compared to traditional methods.

## Features

- Convert XML data into MongoDB documents.
- Handle special XML types, namely SQL Server traces and Procmon traces.
- Automatic data type conversion to match MongoDB's types, such as `int` and `datetime`.
- Option to drop existing collections in the MongoDB database before importing.
- If a specified collection already has records, a new one with a unique name will be created to prevent data mixing.

## Usage

```
python3 ./xmltomongo.py <importfile.xml> [OPTIONS]
```

### Arguments & Options

- `importfile`: Path to the XML file to be imported.
- `-m, --mongodb`: MongoDB connection string. Default is `mongodb://localhost`. For authentication, use the format: `"mongodb://username:password@location:27017/?authSource=admin"`.
- `-d, --database`: Name of the MongoDB database. Default is `sqltrace`.
- `destcollection`: Name of the MongoDB collection to insert to. Default is `trace`.
- `-t`: XML type. Options are "sql" for SQL Server traces and "procmon" for Procmon traces.
- `--drop`: Option to drop collections before importing. Default is `False`.

## MongoDB Usage

Once the trace is imported, you can use a MongoDB client, such as robo3t, to perform various queries:

```
db.trace.distinct("LoginName") // Show every user that logged in
db.trace.sort({"StartTime":1}) // Sort results by start time (ascending)
db.trace.find({"Duration":{$exists:true}}).sort({"Duration":-1}) // Sort by duration, filtering events that have a duration
db.trace.find({"TextData":/arbitraryregex/}) // Search TextData (SQL statements) via regex
db.trace.find({"TextData": /arbitraryregex/}).forEach(function(i){print(i.TextData)}) // Print each SQL query returned by the filter
```

The `forEach` ability in MongoDB allows for faster and more flexible analysis compared to traditional SQL.

## MongoDB Compatibility

The script uses the `pymongo` library for MongoDB connectivity. Supported MongoDB versions are:

- MongoDB 3.6, 4.0, 4.2, 4.4, 5.0, 6.0, and 7.0.

## MongoDB Authentication

The `-m` option accepts MongoDB connection strings, which can include authentication details:

```
python3 ./main.py import.xml sqltrace trace -m "mongodb://username:password@location:27017/?authSource=admin"
```

## Date Handling in Process Monitor Output

MongoDB utilizes full date-time representations for its date values. However, when dealing with Process Monitor output, it's essential to note that the XML trace only provides a time without an associated date. 

As a result, to accommodate this in MongoDB while maintaining the integrity of the time values, all `Time_of_Day` values in the `events` collection for Process Monitor traces are set to have a date of `1900-01-01`. This serves as a placeholder date, ensuring that the time values from the Process Monitor output are preserved accurately.

Users should be aware of this when querying or analyzing the data, ensuring that they account for this placeholder date and focus on the time values for accurate analysis.
