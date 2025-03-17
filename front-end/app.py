import json
import os
from crate import client
from crate.client import Error
from dotenv import load_dotenv
from flask import Flask, render_template

# Load environment variables / secrets from .env file.
load_dotenv()

app = Flask(__name__)

# Connect to CrateDB
conn = client.connect(os.environ["CRATEDB_URL"])

@app.route("/api/networkmap")
def get_network_map():
    agency_name = os.environ["GTFS_AGENCY_NAME"]
    results = { "results": [] }

    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT network FROM networks WHERE agency_name = '{agency_name}'")
        res = cursor.fetchone()
        results["results"].append(json.loads(res[0]))
    finally:
        cursor.close()

    return results

@app.route("/api/routeinfo")
def get_route_colors():
    agency_id = os.environ["GTFS_AGENCY_ID"]
    results = { "results": [] }

    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT route_id, route_short_name, route_long_name, route_color, route_text_color FROM routes WHERE agency_id='{agency_id}'")
        
        for route in cursor.fetchall():
            result = {
                "id": route[0],
                "shortName": route[1],
                "longName": route[2],
                "color": f"#{route[3]}",
                "textColor": f"#{route[4]}"
            }

            results["results"].append(result)
    finally:
        cursor.close()

    return results

@app.route("/api/vehiclepositions")
def get_vehicle_positions():
    agency_id = os.environ["GTFS_AGENCY_ID"]
    results = { "results": [] }

    cursor = conn.cursor()

    try:
        cursor.execute(f"""
            SELECT 
                timestamp, 
                vehicle['trip']['trip_id'], 
                vehicle['vehicle']['label'], 
                vehicle['trip']['route_id'], 
                t.trip_headsign, 
                vehicle['position']['position'], 
                vehicle['current_stop_sequence'] 
            FROM 
                vehicle_positions v, 
                trips t 
            WHERE 
                agency_id = '{agency_id}'
                AND t.trip_id = vehicle['trip']['trip_id'] 
                AND timestamp = (SELECT max(timestamp) FROM vehicle_positions WHERE agency_id = '1')
        """)

        for vehicle in cursor.fetchall():
            result = {
                "timestamp": vehicle[0],
                "tripId": vehicle[1],
                "vehicleId": vehicle[2],
                "line": vehicle[3],
                "destination": vehicle[4],
                "latitude": vehicle[5][0],
                "longitude": vehicle[5][1],
                "currentStopSequence": vehicle[6]
            }

            results["results"].append(result)

    except Error as e:
        # There will be ColumnUnknownExceptions when the front
        # end starts before any real time vehicle data has been
        # stored in the database, these can be ignored.
        if e.message.startswith("ColumnUnknownException"):
            pass
        else:
            print(e)
    finally:
        cursor.close()
    
    return results

@app.route("/api/upcomingstops/<string:trip_id>/<int:current_stop_sequence>/<int:max_to_show>")
def get_upcoming_stops_for_trip(trip_id, current_stop_sequence, max_to_show):
    agency_id = os.environ["GTFS_AGENCY_ID"]
    results = { "results": [] }

    cursor = conn.cursor()

    try:
        # TODO can we get the stop names here rather than IDs?
        # TODO can we limit stop sequences to >= current_stop_sequence in the DB query?
        # TODO which would eliminate the for loop further down.
        cursor.execute(f"""
            SELECT 
                details['stop_time_update'] AS stop_times
            FROM 
                trip_updates 
            WHERE 
                agency_id = '{agency_id}'  
                AND details['trip']['trip_id'] = '{trip_id}'  
            ORDER BY 
                timestamp DESC 
            LIMIT 1
        """)

        upcoming_stops = cursor.fetchall();

        if len(upcoming_stops) > 0:
            # Return only stop sequences >= the provided one...
            # TODO move this work to a database query?
            for upcoming_stop in upcoming_stops[0][0]:
                if upcoming_stop["stop_sequence"] >= current_stop_sequence:
                    results["results"].append({
                        "stopId": upcoming_stop["stop_id"],
                        "stopSequence": upcoming_stop["stop_sequence"],
                        "departure": upcoming_stop["departure"] if "departure" in upcoming_stop else {},
                        "arrival": upcoming_stop["arrival"] if "arrival" in upcoming_stop else {}
                    })
                
                if len(results["results"]) == max_to_show:
                    break
    finally:
        cursor.close()

    return results

@app.route("/api/config")
def get_config():
    agency_id = os.environ["GTFS_AGENCY_ID"]
    results = { "results": [] }

    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT configuration FROM config WHERE agency_id = '{agency_id}'")
        res = cursor.fetchone()
        results["results"].append(res[0])
    finally:
        cursor.close()

    return results


@app.route("/")
def homepage():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(port=int(os.environ["PORT"]))