import csv
import os
import requests
import zipfile

from crate import client
from dotenv import load_dotenv
from io import BytesIO

load_dotenv()

agency_id = os.environ["GTFS_AGENCY_ID"]

# Utility function to load data from a CSV file.
# TODO change this so that the file is in memory.
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
                if file_name == "trips.txt":
                    # We have to do some data type changes here.
                    # 0 route_id TEXT,
                    # 1 service_id TEXT,
                    # 2 trip_id TEXT,
                    # 3 trip_headsign TEXT,
                    # 4 direction_id SMALLINT,
                    # 5 block_id SMALLINT,
                    # 6 shape_id TEXT,
                    # 7 scheduled_trip_id TEXT,
                    # 8 train_id TEXT

                    data_rows.append((
                        row[0],
                        row[1],
                        row[2],
                        row[3],
                        0 if row[4] == "" else int(row[4]),
                        0 if row[5] == "" else int(row[5]),
                        row[6],
                        row[7],
                        row[8]
                    ))

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

# Get the latest GTFS zip file.
def download_gtfs_static_zip():
    print(f"{agency_id}: Downloading the static GTFS zip file.")

    response = requests.get(
        os.environ["GTFS_TRIPS_SCHEDULE_URL"],
        stream = True,
        headers = {
            "Cache-Control": "no-cache",
            "api_key": os.environ["GTFS_TRIPS_SCHEDULE_KEY"] # TODO make auth mechanism an env var
        }
    )

    z = zipfile.ZipFile(BytesIO(response.content))
    print(f"{agency_id}: Downloaded zip file.")

    # TODO Can we do this without writing the file to the filesystem temporarily?
    z.extract("trips.txt")
    print(f"{agency_id}: Extracted trips.txt")

    header_row, data_rows = load_csv_file("trips.txt")

    insert_data("trips", header_row, data_rows)
    print(f"{agency_id}: Stored trips data in database.")

    os.remove("trips.txt")
    print(f"{agency_id}: Removed temporary trips.txt file.")

    # TODO Need to get data from stop_times.txt


download_gtfs_static_zip()