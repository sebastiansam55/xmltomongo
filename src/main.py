#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from pymongo import MongoClient
import argparse
import uuid
import datetime
import time

def try_convert(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return float(value)
        except (ValueError, TypeError):
            try:
                
                if args.type == "sql":
                    #SQL Server profiler timestamp format
                    #<Column id="14" name="StartTime">2023-08-08T09:09:43.887-04:00</Column>
                    return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
                elif args.type == "procmon":
                    #Procmon Time_of_Day timestamp format
                    #<Time_of_Day>10:01:00.0554208 AM</Time_of_Day>
                    time_string_truncated = value[:-4] + value[-3:]
                    return datetime.datetime.strptime(time_string_truncated, '%I:%M:%S.%f %p')
            except (ValueError, TypeError):
                return value

def sql_server_trace(root, mongodb):
    if args.drop:
        print("Dropping trace collection")
        collection.delete_many({})
    for child in root:
        if 'Events' in child.tag:
            count = 0
            for event in child:
                eventname = event.attrib['name']
                eventid = event.attrib['id']
                mongodoc = {"event":eventname, "_id":count}
                for column in event:
                    mongodoc[column.attrib['name']] = try_convert(column.text)
                collection.insert_one(mongodoc)
                count+=1

    print(f"Inserted {count} documents to the {colname} collection on {args.database} database")
    pass

def procmon_trace(root, mongodb):
    process_collection = mongodb["processes"]
    event_collection = mongodb["events"]
    if args.drop:
        print(f"Dropping process and event collections")
        process_collection.delete_many({})
        event_collection.delete_many({})

    for child in root:
        print(child.tag)
        if 'processlist' in child.tag:
            count = 0
            for process in child:
                mongodoc = {"_id":count}
                for column in process:
                    mongodoc[column.tag] = try_convert(column.text)

                process_collection.insert_one(mongodoc)
                count += 1
                if count % 100 == 0:
                    print(f"processed {count} documents")
            print(f"Inserted {count} documents to the processes collection on {args.database} database")
                # print(mongodoc)
        if 'eventlist' in child.tag:
            count = 0
            start = time.time()
            for event in child:
                mongodoc = {"_id":count}
                for column in event:
                    mongodoc[column.tag] = try_convert(column.text)

                event_collection.insert_one(mongodoc)
                count += 1
                if count % 10000 == 0:
                    print(f"processed {count} documents, time elapsed {time.time()-start}")
            print(f"Inserted {count} documents to the event collection on {args.database} database")
                # print(mongodoc)
        pass

if __name__=="__main__":
    parser = argparse.ArgumentParser(
            prog='xmltomongo',
            description='script that converts xml to mongodb documents'
    )
    parser.add_argument('importfile', help="XML File to be imported")
    parser.add_argument('-m','--mongodb', help="MongoDB connection string", default="mongodb://localhost")
    parser.add_argument('database', help="Database to import to", default='sqltrace')
    parser.add_argument('destcollection', help="Collection to insert to", default='trace')
    parser.add_argument('-t', dest="type", help="XML type (sql, procmon)")
    parser.add_argument('--drop', help="Drop collections before importing", action="store_true", default=False)


    args = parser.parse_args()
    CONNECTION_STRING = args.mongodb
    client = MongoClient(CONNECTION_STRING)

    db = client[args.database]
    colname=args.destcollection
    collection = db[colname]

    count = collection.count_documents({})
    if count!=0: # if collection has records create a new one
        colname = 'trace'+str(uuid.uuid4())
        collection = db[colname]
    print(colname)

    print(f"Loading file {args.importfile}")
    tree = ET.parse(args.importfile)
    root = tree.getroot()
    print("XML parse completed")
    if args.type == "sql":
        sql_server_trace(root, db)
    elif args.type == "procmon":
        procmon_trace(root, db)