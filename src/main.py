#!/usr/bin/env python3

import xml.etree.ElementTree as ET
from pymongo import MongoClient
import argparse
import uuid
import datetime
import time
import re
import csv

int_pattern = re.compile(r'^\d+$')
float_pattern = re.compile(r'^\d+\.\d+$')
sql_time_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}T')
eventvwr_time_pattern = sql_time_pattern
procmon_time_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{7} \w{2}$')

strings = [
            # process monitor tags
            "ProcessName", "ImagePath", "CommandLine", "CompanyName", "Version", 
           "Description", "Owner", "Integrity", "Process_Name", "Operation",
           "Path", "Result", "Detail", "AuthenticationId",
           #sql server profiler names
           "NTUserName", "ApplicationName", "LoginName", "DatabaseName", "TextData",
           "Error"
           
           ]
integers = [ # process monitor tags
            "ProcessIndex", "ProcessId", "ParentProcessId", "ParentProcessIndex",
             "CreateTime", "FinishTime", "IsVirtualized", "Is64bit",
             "PID", "Duration"
            # sql server profiler names
            "ClientProcessID", "SPID", "Reads", "Writes", "CPU"
            ]
floats = []
arrays = ["System"]



def try_convert(value, time_pattern):
    if value is None:
        return None
    if bool(int_pattern.match(value)):
        return int(value)
    elif bool(float_pattern.match(value)):
        return float(value)
    elif bool(time_pattern.match(value)):
        if args.type == "sql":
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
        elif args.type == "procmon":
            time_string_truncated = value[:-4] + value[-3:]
            return datetime.datetime.strptime(time_string_truncated, '%I:%M:%S.%f %p')
    else:
        return value
    
def try_convert_by_tag(value, tag):
    if tag in strings:
        return value
    elif tag in integers:
        return int(value)
    elif tag == "Time_of_Day" or tag=="StartTime" or tag=="EndTime":
        if args.type == "procmon":
            time_string_truncated = value[:-4] + value[-3:]
            return datetime.datetime.strptime(time_string_truncated, '%I:%M:%S.%f %p')
        elif args.type == "sql":
            try:
                return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
            except ValueError:
                return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S%z')
    else:
        return try_convert(value)

def eventvwr_trace(root, mongodb):
    print("Starting eventvwr trace import")
    url = "http://schemas.microsoft.com/win/2004/08/events/event"
    def process_array(arr):
        ret={}
        for item in arr:
            if item.text is not None:
                data = item.text.replace(url, "")
                # print(data)
                ret[item.tag.replace("{"+url+"}","")] = try_convert(data, eventvwr_time_pattern)

        return ret



    for events in root:
        # print(child.tag)
        mongodoc = {}
        for event in events:
            # print(event.tag)
            if "System" in event.tag:
                system = process_array(event)
                mongodoc["System"] = system
            if "EventData" in event.tag:
                mongodoc["EventData"] = {}
                for child in event:
                    if "Data" in child.tag:
                        mongodoc["EventData"]["Data"] = child.text
            
        collection.insert_one(mongodoc)

    
def sql_server_trace(root, mongodb):
    if args.drop:
        print("Dropping trace collection")
        collection.delete_many({})
    for child in root:
        if 'Events' in child.tag:
            count = 0
            mongobatch = []
            for event in child:
                eventname = event.attrib['name']
                # eventid = event.attrib['id']
                mongodoc = {"event":eventname, "_id":count}
                for column in event:
                    mongodoc[column.attrib['name']] = try_convert_by_tag(column.text, column.attrib['name'])
                mongobatch.append(mongodoc)
                count+=1
            collection.insert_many(mongobatch)

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
            mongobatch = []
            for process in child:
                mongodoc = {"_id":count}
                for column in process:
                    mongodoc[column.tag] = try_convert_by_tag(column.text, column.tag)

                mongobatch.append(mongodoc)
                count += 1
                if count % 100 == 0:
                    print(f"processed {count} documents")
            process_collection.insert_many(mongobatch)
            print(f"Inserted {count} documents to the processes collection on {args.database} database")
                # print(mongodoc)
        if 'eventlist' in child.tag:
            count = 0
            start = time.time()
            mongobatch = []
            for event in child:
                mongodoc = {"_id":count}
                for column in event:
                    mongodoc[column.tag] = try_convert_by_tag(column.text, column.tag)
                    #TODO add timestamp to capture full perciseness of the 
                    # available data. try_convert literally truncates it otherwise
                    # if column.tag is "Time_of_Day":
                        # mongodoc[timestamp]

                # event_collection.insert_one(mongodoc)
                mongobatch.append(mongodoc)
                count += 1
                if count % 50000 == 0:
                    event_collection.insert_many(mongobatch)
                    print(f"Processed and inserted {count} documents, time elapsed {time.time()-start}")
                    
                    # print(f"Inserted 50000 documents to mongo, {time.time()-start}")
                    mongobatch = []
            event_collection.insert_many(mongobatch)
            print(f"Processed and inserted {count} documents, time elapsed {time.time()-start}")
            print(f"Inserted {count} documents to the event collection on {args.database} database")
                # print(mongodoc)
        pass

def ssv_log(filename, mongodb, headers, strp_format):
    """
    Imports IIS type logs (space separated values). Removes any lines that start with `#`
    """
    with open(filename, 'r') as f:
        read = csv.reader(f, delimiter=' ')
        count = 0
        mongobatch = []
        
        for line in read:
            # print(line[0][0], line)
            if line[0][0]=="#":
                continue

            mongodoc = {"_id":count}
            mongodoc["ts"] = datetime.datetime.strptime(line[0]+line[1], strp_format)
            index = 0
            for item in headers:
                # print(item, index+2, line[index+2])
                mongodoc[item] = try_convert(line[index+2], re.compile("<><><><>"))
                index+=1
            mongobatch.append(mongodoc);

            count+=1

            if count % 50000 == 0:
                collection.insert_many(mongobatch)
                mongobatch = []
        
        collection.insert_many(mongobatch)


if __name__=="__main__":
    parser = argparse.ArgumentParser(
            prog='xmltomongo',
            description='script that converts xml to mongodb documents'
    )
    parser.add_argument('importfile', help="XML File to be imported")
    parser.add_argument('-m','--mongodb', help="MongoDB connection string", default="mongodb://localhost")
    parser.add_argument('database', help="Database to import to", default='sqltrace')
    parser.add_argument('destcollection', help="Collection to insert to", default='trace')
    parser.add_argument('-t', dest="type", help="File type (sql, procmon, eventvwr, iis, httperr)")
    #TODO add to collection
    #parser.add_argument('--append', dest="append", help="Append to existing collection", action="store_true", default=False)
    parser.add_argument('--drop', help="Drop collections before importing", action="store_true", default=False)

    args = parser.parse_args()
    print(args)

    CONNECTION_STRING = args.mongodb
    client = MongoClient(CONNECTION_STRING)

    db = client[args.database]
    colname=args.destcollection
    collection = db[colname]

    count = collection.count_documents({})
    if count!=0: #and not args.append: # if collection has records create a new one
        colname = 'trace'+str(uuid.uuid4())
        collection = db[colname]
    print(colname)

    print(f"Loading file {args.importfile}")
    if args.type == "iis":
        # removed date, time from the headers
        headers = ['s-ip','cs-method','cs-uri-stem','cs-uri-query','s-port','cs-username','c-ip','cs(User-Agent)','cs(Referer)','sc-status','sc-substatus','sc-win32-status','time-taken']
        ssv_log(args.importfile, db, headers, "%Y-%m-%d%H:%M:%S")
    elif args.type == "httperr":
        # removed date, time from the headers
        headers = ['c-ip','c-port','s-ip','s-port','cs-version','cs-method','cs-uri','streamid','sc-status','s-siteid','s-reason','s-queuename']
        ssv_log(args.importfile, db, headers, "%Y-%m-%d%H:%M:%S")
    else:
        
        tree = ET.parse(args.importfile)
        root = tree.getroot()
        print("XML parse completed")
        if args.type == "sql":
            # time_pattern = sql_time_pattern
            sql_server_trace(root, db)
        elif args.type == "procmon":
            # time_pattern = procmon_time_pattern
            procmon_trace(root, db)
        elif args.type == "eventvwr":
            # time_pattern = eventvwr_time_pattern
            eventvwr_trace(root, db)