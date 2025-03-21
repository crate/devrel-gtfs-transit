# Example Queries

The following are some example analyticsal queries that can be run against the dataset.  Note that these are a work in progress and some may require optimization to run efficiently.

## Retrieve the Latest Positions for Each Vehicle

```sql
SELECT DISTINCT (vehicle['vehicle']['id']) 
    id, 
    agency_id, 
    timestamp, 
    vehicle['position']['latitude'] AS latitude,
    vehicle['position']['longitude'] AS longitude,
    vehicle['position']['bearing'] AS bearing
FROM vehicle_positions 
ORDER BY vehicle['vehicle']['id'], timestamp DESC;
```

## What are the Top 10 Average Delays?

```sql
SELECT 
    SPLIT_PART(s.stop_name, ',', 1) AS station_name,  -- Extract station name (before the first comma)
    TRIM(
        SPLIT_PART(SPLIT_PART(s.stop_name, ',', 2), ' LINE', 1) || ' LINE'  -- Extract and clean line name
    ) AS line_name,
    ROUND(AVG(EXTRACT(EPOCH FROM (st.stop_data['arrival']['time'] - st.timestamp))), 3) AS avg_delay_seconds
FROM (
    SELECT 
        unnest(details['stop_time_update']) AS stop_data,
        timestamp
    FROM trip_updates
) st
JOIN stops s ON st.stop_data['stop_id'] = s.stop_id  -- Join with stops table
WHERE st.stop_data['arrival']['time'] IS NOT NULL
GROUP BY station_name, line_name
ORDER BY avg_delay_seconds DESC
LIMIT 10;
```

## What are the Top 10 Average Delays in the Last Hour?

```sql
SELECT 
    SPLIT_PART(s.stop_name, ',', 1) AS station_name,  -- Extract station name before the comma
    TRIM(
        SPLIT_PART(SPLIT_PART(s.stop_name, ',', 2), ' LINE', 1) || ' LINE'  -- Extract and clean line name
    ) AS line_name,
    ROUND(AVG(EXTRACT(EPOCH FROM (st.stop_data['arrival']['time'] - st.details_timestamp))), 3) AS avg_delay_seconds
FROM (
    SELECT 
        unnest(details['stop_time_update']) AS stop_data,
        details['timestamp'] AS details_timestamp  -- Use the real trip update timestamp
    FROM trip_updates
) st
JOIN stops s ON st.stop_data['stop_id'] = s.stop_id  -- Join to get station names
WHERE st.stop_data['arrival']['time'] > EXTRACT(EPOCH FROM NOW()) - 3600  -- Filter last hour
GROUP BY station_name, line_name
ORDER BY avg_delay_seconds DESC
LIMIT 10;
```

## Which are the Top 10 Busiest Stations?

```sql
SELECT 
    SPLIT_PART(s.stop_name, ',', 1) AS station_name, 
    COUNT(*) AS total_stops
FROM (
    SELECT 
        unnest(details['stop_time_update']) AS stop_data
    FROM trip_updates
) st
JOIN stops s ON st.stop_data['stop_id'] = s.stop_id  
GROUP BY station_name
ORDER BY total_stops DESC
LIMIT 10;
```

## How Many Stops are Made at Different Parts of the Day?

```sql
WITH stop_times AS (
    SELECT 
        SPLIT_PART(s.stop_name, ',', 1) AS station_name, 
        CASE 
            WHEN (st.stop_data['arrival']['time'] % 86400) / 3600 BETWEEN 0 AND 5 THEN 'Night'
            WHEN (st.stop_data['arrival']['time'] % 86400) / 3600 BETWEEN 6 AND 11 THEN 'Morning'
            WHEN (st.stop_data['arrival']['time'] % 86400) / 3600 BETWEEN 12 AND 17 THEN 'Afternoon'
            WHEN (st.stop_data['arrival']['time'] % 86400) / 3600 BETWEEN 18 AND 23 THEN 'Evening'
        END AS time_period
    FROM (
        SELECT 
            unnest(details['stop_time_update']) AS stop_data
        FROM trip_updates
    ) st
    JOIN stops s ON st.stop_data['stop_id'] = s.stop_id  
    WHERE st.stop_data['arrival']['time'] IS NOT NULL  -- Remove rows with only departure times
),
ranked_stations AS (
    SELECT 
        time_period,
        station_name,
        COUNT(*) AS total_stops,
        ROW_NUMBER() OVER (PARTITION BY time_period ORDER BY COUNT(*) DESC) AS rank
    FROM stop_times
    WHERE time_period IS NOT NULL  -- Ensure we only count valid time periods
    GROUP BY time_period, station_name
)
SELECT time_period, station_name, total_stops
FROM ranked_stations
WHERE rank = 1  -- Select only the busiest station per period
ORDER BY total_stops DESC;
```

## How Many Active Vehicles are Operating on Each Line in Each Direction?

```sql
SELECT 
    vp.vehicle['trip']['route_id'] AS line_name,  -- Extract line name
    t.trip_headsign AS destination,  -- Extract trip destination
    COUNT(DISTINCT vp.vehicle['vehicle']['id']) AS active_vehicles  -- Count active vehicles
FROM vehicle_positions vp
JOIN trips t 
    ON vp.vehicle['trip']['trip_id'] = t.trip_id  -- Match trips to vehicles
WHERE vp.vehicle['trip']['route_id'] IS NOT NULL  -- Ensure vehicle is assigned to a route
AND vp.vehicle['current_stop_sequence'] > 1  -- Ensure vehicle has moved past its first stop
GROUP BY line_name, destination
ORDER BY active_vehicles DESC, line_name;
```

## Which Stations are Visited Most by Line?

```sql
SELECT 
    vp.vehicle['trip']['route_id'] AS line_name,  
    s.stop_name, 
    COUNT(*) AS stop_visits
FROM vehicle_positions vp
JOIN stops s ON vp.vehicle['stop_id'] = s.stop_id  
WHERE vp.vehicle['trip']['route_id'] IS NOT NULL  
GROUP BY line_name, s.stop_name
ORDER BY stop_visits DESC
LIMIT 10;
```

## What is the Average Dwell Time at Each Stop?

```sql
SELECT 
    s.stop_name, 
    AVG(st.stop_data['departure']['time'] - st.stop_data['arrival']['time']) AS avg_dwell_time_seconds
FROM (
    SELECT 
        unnest(details['stop_time_update']) AS stop_data
    FROM trip_updates
) st
JOIN stops s ON st.stop_data['stop_id'] = s.stop_id  
WHERE st.stop_data['arrival']['time'] IS NOT NULL  
AND st.stop_data['departure']['time'] IS NOT NULL  
GROUP BY s.stop_name
ORDER BY avg_dwell_time_seconds DESC
LIMIT 10;
```

## How does the Number of Active Vehicles Vary Over Time?

```sql
SELECT 
    DATE_TRUNC('hour', TO_TIMESTAMP(vp.timestamp)) AS hour,  
    COUNT(DISTINCT vp.vehicle['vehicle']['id']) AS active_vehicles
FROM vehicle_positions vp
WHERE vp.timestamp > EXTRACT(EPOCH FROM NOW()) - 86400  -- Last 24 hours
GROUP BY hour
ORDER BY hour;
```

## Which Routes have the Most Delays?

```sql
SELECT 
    tu.details['trip']['route_id'] AS line_name,
    ROUND(AVG(tu.stop_data['arrival']['time'] - tu.details['timestamp']), 2) AS avg_delay_seconds
FROM (
    SELECT 
        unnest(details['stop_time_update']) AS stop_data,
        details['timestamp'],
        details['trip']['route_id']
    FROM trip_updates
) tu
WHERE tu.stop_data['arrival']['time'] IS NOT NULL  
GROUP BY line_name
ORDER BY avg_delay_seconds DESC
LIMIT 10;
```