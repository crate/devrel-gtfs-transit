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
                elif file_name == "stop_times.txt":
                    # We have to do some data type changes here.
                    # 0 trip_id TEXT,
                    # 1 arrival_time TEXT,
                    # 2 departure_time TEXT,
                    # 3 stop_id TEXT,
                    # 4 stop_sequence SMALLINT,
                    # 5 pickup_type SMALLINT,
                    # 6 drop_off_type SMALLINT,
                    # 7 shape_dist_traveled DOUBLE PRECISION   

                    data_rows.append((
                        row[0],
                        row[1],
                        row[2], # TODO make this a timestamp.
                        row[3], # TODO make this a timestamp.
                        int(row[4]),
                        0 if row[5] == "" else int(row[5]),
                        0 if row[6] == "" else int(row[6]),
                        float(row[7])
                    ))
                else:
                    print(f"Unknown file format {file_name}.")

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


def process_zipped_file(z, file_name, table_name):
    # TODO Can we do this without writing the file to the filesystem temporarily?
    z.extract(file_name)
    print(f"{agency_id}: Extracted {file_name}")

    header_row, data_rows = load_csv_file(file_name)

    insert_data(table_name, header_row, data_rows)
    print(f"{agency_id}: Stored {table_name} data in database.")

    os.remove(file_name)
    print(f"{agency_id}: Removed temporary {file_name} file.")


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

    process_zipped_file(z, "trips.txt", "trips")
    process_zipped_file(z, "stop_times.txt", "stop_times")


download_gtfs_static_zip()