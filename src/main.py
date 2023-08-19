import xml.etree.ElementTree as ET
from pymongo import MongoClient
import argparse
import uuid
import datetime

def try_convert(value):
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            try:
                return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f%z')
            except ValueError:
                return value

if __name__=="__main__":
    parser = argparse.ArgumentParser(
            prog='xmltomongo',
            description='script that converts xml to mongodb documents'
    )
    parser.add_argument('importfile', help="XML File to be imported")
    parser.add_argument('-m','--mongodb', help="MongoDB connection string", default="mongodb://localhost")
    parser.add_argument('database', help="Database to import to", default='sqltrace')
    parser.add_argument('destcollection', help="Collection to insert to", default='trace')


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


    tree = ET.parse(args.importfile)
    root = tree.getroot()
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