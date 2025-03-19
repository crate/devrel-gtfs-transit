from crate import client
from dotenv import load_dotenv
from google.transit import gtfs_realtime_pb2
from protobuf_to_dict import protobuf_to_dict
from google.protobuf.message import DecodeError
from time import sleep
import os
import requests

# Load environment variables / secrets from .env file.
load_dotenv()

SLEEP_INTERVAL = int(os.environ["SLEEP_INTERVAL"])

def update_vehicle_positions():
    agency_id = os.environ["GTFS_AGENCY_ID"]

    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(
        os.environ["GTFS_POSITIONS_FEED_URL"],
        headers = {
            "Cache-Control": "no-cache",
            "api_key": os.environ["GTFS_POSITIONS_FEED_KEY"] # TODO make auth mechanism an env var
        }
    )

    try:
        feed.ParseFromString(response.content)
        entities = protobuf_to_dict(feed)
    except DecodeError as ex:
        print(f"{agency_id}: Error decoding message:")
        print(ex)
        return

    conn = client.connect(os.environ["CRATEDB_URL"])
    vehicle_position_data = []

    cursor = conn.cursor()

    cursor.execute(f"SELECT max(timestamp) FROM vehicle_positions WHERE agency_id='{agency_id}'")
    res = cursor.fetchone()

    feed_ts = entities["header"]["timestamp"]
    latest_in_db = 0 if res[0] is None else res[0] 

    print(f"{agency_id}: timestamp from feed: {entities["header"]["timestamp"]}, latest in db: {latest_in_db}")

    if feed_ts <= latest_in_db:
        print(f"{agency_id}: Nothing new to store this time.")
        return

    for entity in entities["entity"]:
        # Ignore entries that might be marked as logically deleted.
        if "is_deleted" in entity and entity["is_deleted"] == True:
            continue

        # Tidy up if needed.
        if "is_deleted" in entity:
            del entity["is_deleted"]

        entity["vehicle"]["position"]["position"] = [ entity["vehicle"]["position"]["longitude"], entity["vehicle"]["position"]["latitude"] ]
        timestamp = entity["vehicle"]["timestamp"]
        del entity["vehicle"]["timestamp"]

        # See if we can get the cars that make up the vehicle - WMATA specific.
        if "vehicle" in entity["vehicle"]:
            if "license_plate" in entity["vehicle"]["vehicle"]:
                license_plate_data = entity["vehicle"]["vehicle"]["license_plate"]
                # For DC, license_plate_data looks like this:
                # 8_7566-7567.7480-7481.7716-7717.7409-7408
                # It's how many train cars (8) form up the train
                # followed by the configuration of cars, 
                # the number being the car fleet numbers.
                license_plate_components = license_plate_data.replace('.', '_').replace('-', '_').split('_')
                if (len(license_plate_components) > 0):
                    entity["vehicle"]["vehicle"]["cars"] = license_plate_components[1:]

        vehicle_position_data.append((
            f"""{entity["id"]}-{timestamp}""",
            agency_id,
            feed_ts,
            entity["vehicle"]
        ))

    # https://cratedb.com/docs/python/en/latest/query.html#bulk-inserts
    result = cursor.executemany(
        "INSERT INTO vehicle_positions (id, agency_id, timestamp, vehicle) VALUES (?, ?, ?, ?)",
        vehicle_position_data
    )

    print(f"{agency_id}: Updated {len(entities["entity"])} vehicle positions.")

    cursor.close()

while True:
    update_vehicle_positions()
    sleep(SLEEP_INTERVAL)
