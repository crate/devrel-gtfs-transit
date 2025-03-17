import csv
import json
import os
import sys
from crate import client
from dotenv import load_dotenv

# Load environment variables / secrets from .env file.
load_dotenv()

def create_tables():
    conn = client.connect(os.environ["CRATEDB_URL"])
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agencies (
                agency_id TEXT,
                agency_name TEXT PRIMARY KEY,
                agency_url TEXT,
                agency_timezone TEXT,
                agency_lang TEXT,
                agency_phone TEXT,    
                agency_fare_url TEXT
            )
        """)

        print("Created agencies table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS networks (
                agency_name TEXT PRIMARY KEY,
                agency_id TEXT,
                network TEXT INDEX OFF STORAGE WITH (columnstore = false)
            )
        """)

        print("Created networks table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                route_id TEXT,
                agency_id TEXT,
                route_short_name TEXT,
                route_long_name TEXT,
                route_desc TEXT,
                route_type TEXT,
                route_url TEXT,
                route_color TEXT,
                as_route TEXT,
                network_id TEXT,
                route_text_color TEXT
            )
        """)

        print("Created routes table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicle_positions (
                id TEXT,
                agency_id TEXT,
                timestamp TIMESTAMP,
                vehicle OBJECT(DYNAMIC)
            )
        """)

        print("Created vehicle positions table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trip_updates (
                id TEXT,
                agency_id TEXT,
                timestamp TIMESTAMP,
                details OBJECT(DYNAMIC)
            )
        """)

        print("Created trip updates table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                route_id TEXT,
                service_id TEXT,
                trip_id TEXT,
                trip_headsign TEXT,
                direction_id SMALLINT,
                block_id SMALLINT,
                shape_id TEXT,
                scheduled_trip_id TEXT,
                train_id TEXT
            )
        """)

        print("Created trips table if needed.")

        # TODO make arrival_time and departure_time timestamps.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stop_times (
                trip_id TEXT,
                arrival_time TEXT,
                departure_time TEXT,
                stop_id TEXT,
                stop_sequence SMALLINT,
                pickup_type SMALLINT,
                drop_off_type SMALLINT,
                shape_dist_traveled DOUBLE PRECISION       
            )   
        """)

        print("Created stop_times table if needed.")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                agency_id TEXT PRIMARY KEY,
                configuration OBJECT(DYNAMIC)
            )
        """)

        print("Created config table if needed.")
        print("Finished creating any necessary tables.")
    finally:
        cursor.close()

def load_csv_file(file_name):
    first_row = True

    with open(file_name, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",", quotechar='"')
        header_row = None
        data_rows = []

        for row in reader:
            if (first_row):
                first_row = False
                header_row = row
            else:
                data_rows.append(tuple(row))

    return (header_row, data_rows)


def insert_data(table_name, column_names, rows):
    conn = client.connect(os.environ["CRATEDB_URL"])
    cursor = conn.cursor()

    try:
        cursor.executemany(
            f"INSERT INTO {table_name} ({','.join([str(s) for s in column_names])}) VALUES ({','.join(['?'] * len(column_names))})", 
            rows
        )
    finally:
        cursor.close()

def load_config_data(file_name):
    with open(file_name) as config_file:
        conf = json.load(config_file)

    conn = client.connect(os.environ["CRATEDB_URL"])
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO config (agency_id, configuration) VALUES (?, ?)",
            (conf["agencyId"], json.dumps(conf["configuration"]))
        )
    finally:
        cursor.close()

    print("Inserted network data.")
    

def load_agency_data(file_name):
    header_row, data_rows = load_csv_file(file_name)
    insert_data("agencies", header_row, data_rows)
    print("Inserted agency data.")


def load_route_data(file_name):
    header_row, data_rows = load_csv_file(file_name)
    insert_data("routes", header_row, data_rows)
    print("Inserted route data.") 
    

def load_network_data(file_name, agency_name):
    with open(file_name) as geojson_file:
        geojson = json.load(geojson_file)
    
    conn = client.connect(os.environ["CRATEDB_URL"])
    cursor = conn.cursor() 

    try:
        cursor.execute(
            "INSERT INTO networks (agency_name, network) VALUES (?, ?)",
            (agency_name, json.dumps(geojson))
        )
    finally:
        cursor.close()

    print("Inserted network data.")

if len(sys.argv) < 2:
    print("You need to pass in a file name and/or other parameters!")
elif len(sys.argv) == 2 and sys.argv[1] == "createtables":
    create_tables()
elif len(sys.argv) == 2 and sys.argv[1].endswith("agency.txt"):
    load_agency_data(sys.argv[1])
elif len(sys.argv) == 2 and sys.argv[1].endswith("routes.txt"):
    load_route_data(sys.argv[1])
elif len(sys.argv) == 2 and sys.argv[1].endswith(".json"):
    load_config_data(sys.argv[1])
elif len(sys.argv) == 3 and sys.argv[1].endswith(".geojson"):
    load_network_data(sys.argv[1], sys.argv[2])
else:
    print("Invalid usage.")
