/*
 * L.TileLayer.Grayscale is a regular tilelayer with grayscale makeover.
 * https://github.com/Zverik/leaflet-grayscale/
 */

L.TileLayer.Grayscale = L.TileLayer.extend({
	options: {
		quotaRed: 21,
		quotaGreen: 71,
		quotaBlue: 8,
		quotaDividerTune: 0,
		quotaDivider: function() {
			return this.quotaRed + this.quotaGreen + this.quotaBlue + this.quotaDividerTune;
		}
	},

	initialize: function (url, options) {
		options = options || {}
		options.crossOrigin = true;
		L.TileLayer.prototype.initialize.call(this, url, options);

		this.on('tileload', function(e) {
			this._makeGrayscale(e.tile);
		});
	},

	_createTile: function () {
		var tile = L.TileLayer.prototype._createTile.call(this);
		tile.crossOrigin = "Anonymous";
		return tile;
	},

	_makeGrayscale: function (img) {
		if (img.getAttribute('data-grayscaled'))
			return;

    img.crossOrigin = '';
		var canvas = document.createElement("canvas");
		canvas.width = img.width;
		canvas.height = img.height;
		var ctx = canvas.getContext("2d");
		ctx.drawImage(img, 0, 0);

		var imgd = ctx.getImageData(0, 0, canvas.width, canvas.height);
		var pix = imgd.data;
		for (var i = 0, n = pix.length; i < n; i += 4) {
      pix[i] = pix[i + 1] = pix[i + 2] = (this.options.quotaRed * pix[i] + this.options.quotaGreen * pix[i + 1] + this.options.quotaBlue * pix[i + 2]) / this.options.quotaDivider();
		}
		ctx.putImageData(imgd, 0, 0);
		img.setAttribute('data-grayscaled', true);
		img.src = canvas.toDataURL();
	}
});

L.tileLayer.grayscale = function (url, options) {
	return new L.TileLayer.Grayscale(url, options);
};

/* ---- End Grayscale code ---- */

const myMap = L.map('mapId');
const stopMarkers = L.layerGroup();
const vehicleMarkers = L.layerGroup();

myMap.addLayer(stopMarkers);
myMap.addLayer(vehicleMarkers);

let config;
let routeInfo;
let stopNames;
let interval;

async function getConfiguration() {
  const response = await fetch('/api/config');
  const responseObj = await response.json();

  return responseObj.results[0];
}

async function getSystemInfo() {
  const response = await fetch('/api/routeinfo');
  const responseObj = await response.json();

  return responseObj.results;
}

async function getStopNames() {
  const response = await fetch('/api/stopnames');
  const responseObj = await response.json();

  return responseObj.results[0];
}

function getRefreshInterval() {
  const refreshElement = document.getElementById('autoRefreshInterval');
  return parseInt(refreshElement.options[refreshElement.selectedIndex].text, 10) * 1000;
}

async function drawRouteMap() {
  const response = await fetch('/api/networkmap');
  const routeMap = await response.json();

  L.geoJSON(routeMap.results[0], {
    style: {
      color: '#000000',
      weight: 1
    },
    pointToLayer: function (feature, latlng) {
      const stopMarker = L.circleMarker(latlng, {
        radius: 7,
        fillColor: '#0000000',
        opacity: 0.5,
        fillOpacity: 0.5
      });

      stopMarkers.addLayer(stopMarker);
      return stopMarker;
    },
    onEachFeature: function (feature, layer) {
      if (feature.properties && feature.properties.stop_id) {
        layer.bindPopup(`<h2>${feature.properties.stop_name}</h2><p>ID: ${feature.properties.stop_id}</p>`);
      }
    }
  }).addTo(myMap);
}

async function updateVehicleLocations() {
  const response = await fetch('/api/vehiclepositions');
  const responseDoc = await response.json();

  function getMarkerColor(line) {
    const r = routeInfo.filter(r => r.id === line);
    return (r.length === 1 ? r[0].color : '#000000');
  }

  vehicles = responseDoc.results;

  let openPopupId;

  // Is a popup currently open?
  for ( const vehicleMarker of vehicleMarkers.getLayers()) {
    const popup = vehicleMarker.getPopup();
    if (popup && popup.isOpen()) {
      openPopupId = vehicleMarker.options.vehicle.tripId;
    }
  }

  vehicleMarkers.clearLayers();

  for (const vehicle of vehicles) {
    const markerColor = getMarkerColor(vehicle.line);
  
    const vehicleMarker = L.circleMarker([vehicle.longitude, vehicle.latitude], {
      radius: 5,
      color: markerColor,
      fillColor: markerColor,
      fillOpacity: 1,
      vehicle: {
        cars: vehicle.cars || [],
        tripId: vehicle.tripId,
        vehicleId: vehicle.vehicleId,
        line: vehicle.line,
        destination: vehicle.destination,
        licensePlate: vehicle.licensePlate,
        currentStopSequence: vehicle.currentStopSequence
      }
    });

    vehicleMarker.on('popupopen', async function(e) {
      this.setPopupContent(`
        <h2>Loading data...</h2>
      `);

      let popupContent = `<h2>${this.options.vehicle.line} to ${this.options.vehicle.destination}</h2><p>${this.options.vehicle.tripId}</p>`;
      if (this.options.vehicle.cars && this.options.vehicle.cars.length > 0) {
        popupContent = `${popupContent}<p>${this.options.vehicle.cars.length} cars.</p>`;
      }

      if (this.options.vehicle.currentStopSequence) {
        const upcomingStopsResponse = await fetch(`/api/upcomingstops/${this.options.vehicle.tripId}/${this.options.vehicle.currentStopSequence}/${config.upcomingStopsToShow}`);
        const upcomingStopsResults = await upcomingStopsResponse.json();
  
        popupContent = `${popupContent}<h3>Next Stops:</h3><ol></ol>`;
        for (const upcomingStop of upcomingStopsResults.results) {
          const nowTime = Math.floor(Date.now() / 1000);
          let stopTime = Math.round(upcomingStop.arrival.time ? (upcomingStop.arrival.time - nowTime) / 60 : 0);

          if (stopTime >= 0) {
            popupContent = `${popupContent}<li>(${stopTime} min${stopTime > 1 ? 's': ''}) ${stopNames[upcomingStop.stopId]}</li>`
          }
        }
  
        popupContent = `${popupContent}</ol>`;
  
      }

      this.setPopupContent(popupContent);
    });

    vehicleMarker.bindPopup('');
    vehicleMarkers.addLayer(vehicleMarker);

    if (openPopupId && openPopupId == vehicle.tripId) {
      vehicleMarker.openPopup();
    }
  }
}

(async () => {
  config = await getConfiguration();

  myMap.setView([config.initialLatitude, config.initialLongitude], config.initialZoom);

  L.tileLayer.grayscale(
    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', 
    {
      maxZoom: config.maxZoom,
      opacity: 0.5,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }
  ).addTo(myMap);
  
  myMap.setMaxBounds(myMap.getBounds());
  myMap.setMinZoom(config.initialZoom);
  
  routeInfo = await getSystemInfo();
  stopNames = await getStopNames();

  await drawRouteMap();
  updateVehicleLocations();

  interval = setInterval(updateVehicleLocations, getRefreshInterval());

  document.getElementById('autoRefresh').addEventListener('change', e => {
    const intervalSelect = document.getElementById('autoRefreshInterval');

    if (e.currentTarget.checked) {
      intervalSelect.removeAttribute('disabled');
      interval = setInterval(updateVehicleLocations, getRefreshInterval());
    } else {
      intervalSelect.setAttribute('disabled', '');
      clearInterval(interval);
    }
  });

  document.getElementById('showStops').addEventListener('change', e => {
    if (e.currentTarget.checked) {
      myMap.addLayer(stopMarkers);
    } else {
      myMap.removeLayer(stopMarkers);
    }
  });

  document.getElementById('autoRefreshInterval').addEventListener('change', e => {
    clearInterval(interval);
    interval = setInterval(updateVehicleLocations, getRefreshInterval());
  });
})();