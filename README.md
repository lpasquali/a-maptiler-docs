# A way serve tiles for airgapped systems based Ubuntu noble


## Configure ubuntu packlages and pip

Solution relies only on packages distributed by the OS itself, in this case is tested for Ubuntu 24.04 Noble.
the provided list of packages is for arm64 architecture, to run on amd64 please edit it and change everywhere 
"arm64" with "amd64".<br/>
Login into the Ubuntu Noble system created for this exercise, and perform:

```bash
sudo apt-get install -y \
  apache2 apache2-bin apache2-data apache2-utils \
  gdal-bin gdal-data gdal-plugins \
  git git-man \
  libapache2-mod-tile \
  libgdal34t64 \
  libmapnik3.1t64 \
  mapnik-reference mapnik-utils \
  node-carto nodejs nodejs-doc \
  osm2pgsql osmctools \
  postgis postgis-doc \
  postgresql-16 postgresql-16-postgis-3 postgresql-16-postgis-3-scripts \
  postgresql-client-16 postgresql-client-common postgresql-common \
  postgresql-postgis postgresql-postgis-scripts \
  python3-gdal python3-psycopg2 python3-pyosmium \
  renderd python3-venv
```

Then setup a python virtual environment and install the required python packages:

```bash
git clone https://github.com/lpasquali/a-maptiler-docs.git
cd ~/a-maptiler-docs
python3 -m venv maptile
source ./maptile/bin/activate
pip install -r ./requirements.txt
```

to setup correctly the tool and also the rendering engine which will serve the tiles in your final application, you need to note down the bounding box of your area of interest, and the center point (lat, lon) to start the map from.

```bash
# City of Milano
python bbox.py Milano
# City of Vancouver
python bbox.py Vancouver
# State of Alberta
python bbox.py Alberta
# State of Colombia
python bbox.py CO
# Principality of Andorra
python bbox.py AD
# Region of Sardinia
python bbox.py Sardegna
```

once done please run:
```bash
deactivate
```

## Configure the mapnik style "openstreetmap-carto"


### Get repo ans start setting up postgres

Perform the following commands:

```bash
git clone https://github.com/gravitystorm/openstreetmap-carto.git
cd openstreetmap-carto
sudo -u postgres createuser -s $USER
createdb gis
psql -d gis -c 'CREATE EXTENSION postgis; CREATE EXTENSION hstore;'
psql -d gis -c 'ALTER SYSTEM SET jit=off;' -c 'SELECT pg_reload_conf();'
```


### Install the desired portion of worldmap to be served as tiles

You need to search pbf files in a site like [https://download.geofabrik.de](https://download.geofabrik.de)

Note: not always you will find the section you need for your business application, in that case you can use this method:
```bash
#extract Sidney from Australia
sudo apt install osmium-tool
wget https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf
osmium extract --strategy complete_ways --bbox 150.260825,-34.1732416,151.343898,-33.3641864 australia-latest.osm.pbf -o sidney.pbf
osm2pgsql -O flex -S openstreetmap-carto-flex.lua -d gis ../sidney.pbf
```

Example of Andorra:

```bash
#experiment covers Principality of Andorra
sudo apt install osmium-tool
wget https://download.geofabrik.de/europe/andorra-latest.osm.pbf

osm2pgsql -O flex -S openstreetmap-carto-flex.lua -d gis andorra-latest.osm.pbf
```

### Finalize the mapnik style setup

```bash



# create indexes in parallel
# scripts/indexes.py -0 | xargs -0 -P0 -I{} psql -d gis -c "{}"

psql -d gis -f indexes.sql
psql -d gis -f functions.sql
scripts/get-external-data.py
scripts/get-fonts.py
sudo -u postgres createuser -s _renderd
sudo -u postgres psql -d gis -c 'GRANT CONNECT ON DATABASE gis TO _renderd;'
sudo -u postgres psql -d gis -c 'GRANT SELECT ON ALL TABLES IN SCHEMA public TO _renderd;'
sudo -u postgres psql -d gis -c 'GRANT USAGE ON schema public TO _renderd;'
sudo mkdir /var/www/osm/
```

Generate the mapnik style xml file in `project.mml`:

```bash

carto project.mml > style.xml

sudo mkdir /etc/mapnik-osm-carto-data/
sudo cp -a fonts symbols patterns style.xml /etc/mapnik-osm-carto-data/
```

## Configure the html + js static tool to check the maps from a browser.

Even if the solution is thought for a pragmatical access from some microservice which will use these tiles as a background for vectors or rasters eventually coming from business logic, it is useful to have a tool to check the map tiles from a browser.


create this file under `/var/www/osm/slippymap.html`

```bash
cat << EOF | sudo tee /var/www/osm/slippymap.html
<html>
<head>
    <title>OSM Local Tiles</title>
    <link rel="stylesheet" href="style.css" type="text/css" />
    <!-- bring in the OpenLayers javascript library
         (here we bring it from the remote site, but you could
         easily serve up this javascript yourself) -->
    <script src="OpenLayers.js"></script>
 
    <!-- bring in the OpenStreetMap OpenLayers layers.
         Using this hosted file will make sure we are kept up
         to date with any necessary changes -->
    <script src="OpenStreetMap.js"></script>
 
    <script type="text/javascript">
// Start position for the map (hardcoded here for simplicity)
        var lat=47.7;
        var lon=7.5;
        var zoom=10;
 
        var map; //complex object of type OpenLayers.Map
 
        //Initialise the 'map' object
        function init() {
 
            map = new OpenLayers.Map ("map", {
                controls:[
                    new OpenLayers.Control.Navigation(),
                    new OpenLayers.Control.PanZoomBar(),
                    new OpenLayers.Control.Permalink(),
                    new OpenLayers.Control.ScaleLine({geodesic: true}),
                    new OpenLayers.Control.Permalink('permalink'),
                    new OpenLayers.Control.MousePosition(),                    
                    new OpenLayers.Control.Attribution()],
                maxExtent: new OpenLayers.Bounds(-20037508.34,-20037508.34,20037508.34,20037508.34),
                maxResolution: 156543.0339,
                numZoomLevels: 19,
                units: 'm',
                projection: new OpenLayers.Projection("EPSG:900913"),
                displayProjection: new OpenLayers.Projection("EPSG:4326")
            } );
 
            // This is the layer that uses the locally stored tiles
            var newLayer = new OpenLayers.Layer.OSM("Local Tiles", "\${z}/\${x}/\${y}.png", {numZoomLevels: 19});
            map.addLayer(newLayer);

            layerMapnik = new OpenLayers.Layer.OSM.Mapnik("Mapnik");
            map.addLayer(layerMapnik);

// This is the end of the layer
 
            var switcherControl = new OpenLayers.Control.LayerSwitcher();
            map.addControl(switcherControl);
            switcherControl.maximizeControl();
 
            if( ! map.getCenter() ){
                var lonLat = new OpenLayers.LonLat(lon, lat).transform(new OpenLayers.Projection("EPSG:4326"), map.getProjectionObject());
                map.setCenter (lonLat, zoom);
            }
        }
 
    </script>
</head>
 
<!-- body.onload is called once the page is loaded (call the 'init' function) -->
<body onload="init();">
 
    <!-- define a DIV into which the map will appear. Make it take up the whole window -->
    <div style="width:100%; height:100%" id="map"></div>
 
</body>
 
</html>
EOF
```

If needed it is possible to change map's start position in hmtl above using the provided script  `bbox.py` to get the center of your area of interest.

Then download the required images and js files for the map to work:

```bash
cd /var/www/osm
sudo mkdir -p theme/default
sudo wget http://www.openstreetmap.org/openlayers/img/blank.gif
sudo wget http://www.openstreetmap.org/openlayers/img/cloud-popup-relative.png
sudo wget http://www.openstreetmap.org/openlayers/img/drag-rectangle-off.png
sudo wget http://www.openstreetmap.org/openlayers/img/drag-rectangle-on.png
sudo wget http://www.openstreetmap.org/openlayers/img/east-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/layer-switcher-maximize.png
sudo wget http://www.openstreetmap.org/openlayers/img/layer-switcher-minimize.png
sudo wget http://www.openstreetmap.org/openlayers/img/marker.png
sudo wget http://www.openstreetmap.org/openlayers/img/marker-blue.png
sudo wget http://www.openstreetmap.org/openlayers/img/marker-gold.png
sudo wget http://www.openstreetmap.org/openlayers/img/marker-green.png
sudo wget http://www.openstreetmap.org/openlayers/img/measuring-stick-off.png
sudo wget http://www.openstreetmap.org/openlayers/img/measuring-stick-on.png
sudo wget http://www.openstreetmap.org/openlayers/img/north-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/panning-hand-off.png
sudo wget http://www.openstreetmap.org/openlayers/img/panning-hand-on.png
sudo wget http://www.openstreetmap.org/openlayers/img/slider.png
sudo wget http://www.openstreetmap.org/openlayers/img/south-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/west-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/zoombar.png
sudo wget http://www.openstreetmap.org/openlayers/img/zoom-minus-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/zoom-plus-mini.png
sudo wget http://www.openstreetmap.org/openlayers/img/zoom-world-mini.png
sudo wget http://openlayers.org/api/theme/default/style.css
sudo wget http://www.openlayers.org/api/OpenLayers.js
sudo wget http://www.openstreetmap.org/openlayers/OpenStreetMap.js
sudo cp style.css theme/default/
sudo mkdir -p img
sudo mv *.png *.gif img/
```

## Configure renderd 

Create config file `/etc/renderd.conf`:

```bash
cat << EOF | sudo tee /etc/renderd.conf
; BASIC AND SIMPLE CONFIGURATION:

[renderd]
stats_file=/run/renderd/renderd.stats
socketname=/run/renderd/renderd.sock
num_threads=4
tile_dir=/var/cache/renderd/tiles

[mapnik]
plugins_dir=/usr/lib/mapnik/3.1/input
font_dir=/usr/share/fonts/truetype
font_dir_recurse=true

; ADD YOUR LAYERS:
[default]
XML=/etc/mapnik-osm-carto-data/style.xml
TILESIZE=512
URI=/osm/
DESCRIPTION=This is the standard osm mapnik style
EOF
```


## Configure apache 

Create following VirtualHost in apache configuration directory `/etc/apache2/sites-available/001_tile.conf`:

```bash
cat << EOF | sudo tee /etc/apache2/sites-available/001_tile.conf
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    ServerName localhost
    DocumentRoot /var/www
    LogLevel info
    Header always set Referrer-Policy "strict-origin-when-cross-origin"
    ModTileTileDir /var/cache/renderd/tiles
    LoadTileConfigFile /etc/renderd.conf
    ModTileRequestTimeout 2
    ModTileMissingRequestTimeout 10
    ModTileMaxLoadOld 2
    ModTileMaxLoadMissing 20
    ModTileRenderdSocketName /var/run/renderd/renderd.sock
    ModTileCacheDurationMax 604800
    ModTileCacheDurationDirty 900
    ModTileCacheDurationMinimum 10800
    ModTileCacheDurationMediumZoom 13 86400
    ModTileCacheDurationLowZoom 9 518400
    ModTileCacheLastModifiedFactor 0.20
    ModTileEnableTileThrottling Off
    ModTileEnableTileThrottlingXForward 0
    ModTileThrottlingTiles 10000 1 
    ModTileThrottlingRenders 128 0.2
    <Directory />
      Options FollowSymLinks
      AllowOverride None
    </Directory>
    <Directory /var/www/>
      Options Indexes FollowSymLinks MultiViews
      AllowOverride None
      Order allow,deny
      allow from all
    </Directory>
    ScriptAlias /cgi-bin/ /usr/lib/cgi-bin/
    <Directory "/usr/lib/cgi-bin">
      AllowOverride None
      Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
      Order allow,deny
      Allow from all
    </Directory>
    Alias /doc/ "/usr/share/doc/"
    <Directory "/usr/share/doc/">
      Options Indexes MultiViews FollowSymLinks
      AllowOverride None
      Order deny,allow
      Deny from all
      Allow from 127.0.0.0/255.0.0.0 ::1/128
    </Directory>
</VirtualHost>
EOF
```

perform:

```bash
sudo a2enmod tile
sudo a2enmod headers
sudo a2dissite 000-default
sudo a2ensite 001_tile
sudo systemctl restart renderd
sudo systemctl restart apache2
```

## Speeding up tile rendering

You can speed up the tile rendering by pre-rendering tiles for your area of interest, by bounding box and zoom levels.

Example of Andorra from zoom level 1 to 18:

```bash
cd ~/a-maptiler-docs
source ./maptile/bin/activate
python bbox.py AD
```
Results in:

```python
Type: Country
Name: Andorra
Bounding box: (1.41484375, 42.4344726562, 1.740234375, 42.6427246094)
Center: (1.5775390625, 42.5385986328)
```

Then you can run the following loop to render all tiles from zoom level 1 to 18 for the bounding box of Andorra:

```bash

for num in $(seq 1 18); do render_list -z $num -Z $num -n 8 -l 50 -x 42.4344726562 -X 42.6427246094 -y 1.41484375 -Y 1.740234375 --all; done

```

## Useful readings

https://medium.com/analytics-vidhya/how-to-generate-lat-and-long-coordinates-of-city-without-using-apis-25ebabcaf1d5
https://www.gps-coordinates.net/
https://wiki.openstreetmap.org/wiki/OpenLayers_Local_Tiles_Example
https://nominatim.org/release-docs/latest/admin/Installation/
https://operations.osmfoundation.org/policies/nominatim/
https://github.com/gravitystorm/openstreetmap-carto/blob/master/INSTALL.md