import datetime
import os
import subprocess
import urllib.request
from time import sleep
from branca.element import Template, MacroElement
import geopandas as geopandas
#from pylab import text
import branca.colormap as cm
import folium
import matplotlib.pyplot as plt
import numpy as np
import requests
import typer
import xarray
import rioxarray
from shapely.geometry import mapping
from PIL import Image, ImageChops
from bs4 import BeautifulSoup
from cartopy import crs as ccrs
from cartopy.mpl.ticker import LongitudeFormatter, LatitudeFormatter






def trim(img):
    border = Image.new(img.mode, img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, border)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        img = img.crop(bbox)
    return np.array(img)


def read_img(name):
    img = Image.open(name)
    img = trim(img)
    return img


def add_gif(m, name, gif_file, bounds, flag):
    feature_group = folium.FeatureGroup(name=name, show=flag)
    image_overlay = folium.raster_layers.ImageOverlay(gif_file, bounds=bounds, opacity=0.5, pixelated=False)
    feature_group.add_child(image_overlay)
    feature_group.add_to(m)


def listFD(url, ext=''):
    page = requests.get(url).text
    soup = BeautifulSoup(page, 'html.parser')
    return [url + '/' + node.get('href') for node in soup.find_all('a') if node.get('href').endswith(ext)]


def map_settings(ax, lon_ticks, lat_ticks, domain):
    # Set up and label the lat/lon grid
    ax.xaxis.set_major_formatter(LongitudeFormatter())
    ax.yaxis.set_major_formatter(LatitudeFormatter())
    ax.set_extent(domain, crs=ccrs.PlateCarree())


def main(save_path):
    minute = '{:02d}'.format(datetime.datetime.now().minute)
    hour = '{:02d}'.format(datetime.datetime.now().hour)
    day = '{:02d}'.format(datetime.datetime.now().day)
    month = '{:02d}'.format(datetime.datetime.now().month)
    year = datetime.datetime.now().year
   # if 18<datetime.datetime.now().hour:
   #     day = '{:02d}'.format((datetime.date.today() + datetime.timedelta(days=1)).day)
   #     month = '{:02d}'.format((datetime.date.today() + datetime.timedelta(days=1)).month)
   #     year = (datetime.date.today() + datetime.timedelta(days=1)).year

    url = f'https://mtarchive.geol.iastate.edu/{year}/{month}/{day}/mrms/ncep/PrecipRate/'
    ext = 'gz'

    print('downloading file ...')
    os.chdir(save_path)
    target = listFD(url,ext)
    if not target:
        print('no files')
        quit()
    target.sort()
    file = target[-1]
    urllib.request.urlretrieve(file, "mrms.grib2.gz")
    print('converting ...')
    subprocess.check_call(["gunzip", '-f', 'mrms.grib2.gz'])
    subprocess.check_call(["grib_to_netcdf", 'mrms.grib2', '-o', 'mrms.nc'])
    print('cropping ...')

    xds = xarray.open_dataset("mrms.nc")
    xds.rio.set_spatial_dims(x_dim="longitude", y_dim="latitude", inplace=True)
    xds.rio.write_crs("epsg:4326", inplace=True)
    # xds = xds.rio.clip_box(minx=276, miny=36, maxx=295, maxy=50)
    lat_min = 20
    lat_max = 54.99
    lon_min = -130
    lon_max = -60
    aod = xds['unknown'].data
    aod = aod[0]
    aod[-1][-1] = 50
    aod[0][0] = 0
    aod[aod <= 0.01] = None
    lon = xds['longitude'].data
    lat = xds['latitude'].data
    lon -= 360
    print('saving png ...')

    domain = [lon_min, lon_max, lat_min, lat_max]  # Boundaries of map: [western lon, eastern lon, southern lat, northern lat]
    lon_ticks = [-81, -73, -64]
    lat_ticks = [36, 38, 41, 44]

    fig = plt.figure(figsize=(8, 10))
    ax = plt.axes(projection=ccrs.PlateCarree())

    map_settings(ax, lon_ticks, lat_ticks, domain)

    bar = 'rainbow'  # Color map for colorbar and plot
    max_color = 'darkred'  # Color for Rad data > 1

    # Plotting settings for AOD data
    color_map = plt.get_cmap(bar)
    color_map.set_over(max_color)

    # Create filled contour plot of AOD data
    # levels = np.arange(0, 50, 0.5)
    #text(0.8, 0.1, f'{hour}:{minute}{month}/{day}/{year} EST', ha='center',
    #     va='center', transform=ax.transAxes, c='#fff')

    #pcm = ax.contourf(lon, lat, aod,
    #                  cmap=color_map)  # ,  levels=levels, extend='both', zorder=2.5, transform=ccrs.PlateCarree())
    from matplotlib import colors
    levels = [0,0.1,0.2,0.5,1,2,4,6,8,10,15,20,30,40,50]
    norm = colors.BoundaryNorm(levels, len(levels))

    pcm = ax.contourf(lon, lat, aod,#cmap=color_map,
                      norm=norm, levels=levels, extend='both', colors=('#606060', '#67627D', '#5F5B8E', '#4B67AB',
                                                                       '#4A9BAC', '#56B864', '#91CE4E','#D0DB45',
                                                                       '#DBB642','#DB9D48','#DB7B50','#D15F5E',
                                                                       '#B43A66','#93164E','#541029')) 
    fig.patch.set_visible(False)
    ax.axis('off')
    file_res = 2000
    name = f'{save_path}/img/MRMS{year}{month}{day}{hour}{minute}.png'
    fig.savefig(name, bbox_inches='tight', dpi=file_res, pad_inches=0)

    # # make the vid
    files = {os.path.getmtime(os.path.join(save_path, 'img', f)) : os.path.join(save_path, 'img', f) for f in os.listdir(os.path.join(save_path, 'img')) if
             os.path.isfile(os.path.join(save_path, 'img', f)) and f.endswith('png')}
    file_times = [e for e in list(files)]
    file_times.sort()
    if len(file_times) > 8:
        files_to_keep = file_times[-8:]
        files_to_delete = [e for e in file_times if e not in files_to_keep]
        for _file in files_to_delete:
            subprocess.check_call(["rm", files[_file]])

    # Get the name of the files
    file_names = {os.path.getmtime(os.path.join(save_path, 'img', f)) : os.path.join(save_path, 'img', f) for f in os.listdir(os.path.join(save_path, 'img')) if
             os.path.isfile(os.path.join(save_path, 'img', f)) and f.endswith('png')}
    import collections
    od = collections.OrderedDict(sorted(file_names.items()))
    od = [od[_key][-16:-4] for _key in list(od)]
    od = [f'{_key[8:10]}:{_key[10:]} {_key[4:6]}/{_key[6:8]}/{_key[:4]} UTC' for _key in od]

    # subprocess.check_call(["convert", "-delay", '100', '-loop', '0', 'img/*.png', 'img/mrms.gif'])

    from subprocess import Popen, PIPE, STDOUT

    cmd = f"convert -delay 100 -loop 0 -dispose background {save_path}/img/*.png {save_path}/img/mrms.gif"
    p = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True)
    output = p.stdout.read()
    print(output)


    print('loading images on folium ...')
    colormap = cm.LinearColormap(colors=['darkblue', 'blue', 'cyan', 'yellow', 'orange', 'red'],
                                 index=[0, 25, 62.5, 156.25, 390.6, 1000],
                                 vmin=0, vmax=1000,
                                 )

    _url = 'https://server.arcgisonline.com/ArcGIS/rest/services/Specialty/DeLorme_World_Base_Map/MapServer/tile/{z}/{y}/{x}'

    m = folium.Map([40.749044, -73.983306],
                   # tiles='cartodbdark_matter',
                   tiles='cartodbpositron',
                   zoom_start=6,
                   min_zoom=4,
                   max_zoom=10,
                   prefer_canvas=True
                   )


#     folium.LayerControl(collapsed=False).add_to(m)

    from folium.plugins import FloatImage
    url = (
        "MRMS.png"
    )
    FloatImage(url, bottom=80, left=5).add_to(m)

    template = """
    {% macro html(this, kwargs) %}

   <!doctype html>
<html lang="en">
     <!doctype html>
<html lang="en">
<head>

        <meta charset="UTF-8">
        <meta http-equiv="X-UA-Compatible" content="IE=edge">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Document</title>
     
       
    </head>
    <body>
        
   
    
    


  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>jQuery UI Draggable - Default functionality</title>
  <link rel="stylesheet" href="//code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css">

  <script src="https://code.jquery.com/jquery-1.12.4.js"></script>
  <script src="https://code.jquery.com/ui/1.12.1/jquery-ui.js"></script>

  <script>
  $( function() {
    $( "#maplegend" ).draggable({
                    start: function (event, ui) {
                        $(this).css({
                            right: "auto",
                            top: "auto",
                            bottom: "auto"
                        });
                    }
                });
});

  </script>


<div id='maplegend' class='maplegend' 
    style='position: absolute; z-index:9999;
     border-radius:0px; padding: 10px; font-size:14px; right: 21px; bottom: 20px;'>
      <span  valign="middle"; align="center"; style="background-color: transparent ; color: black;font-weight: bold; font-size: 180%; " id="txt" ></span>

<div class='legend-scale'>
  <ul class='legend-labels'>
      
    

       <li><span valign="middle"; align="center"; style="background: rgb(255, 255, 255); color: rgb(0, 0, 0);font-weight: bold; font-size: 100%;">  Inch  </span></li>
     <li><span valign="middle"; align="center"; style="background: rgba(255, 0, 0); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">  2  </span></li>
     <li><span valign="middle"; align="center"; style="background: rgba(225, 90, 0); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">  1.5  </span></li>
         <li><span valign="middle"; align="center"; style="background:  rgba(234, 162, 62, 0.87); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">  1  </span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(255,255,0); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">0.8</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(193, 229, 60, 0.87); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">0.5</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(153, 220, 69, 0.87); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">0.2</span></li>
    <li><span valign="middle"; align="center";  style="background: rgba(69, 206, 66, 0.87); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">0.12</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(78, 194, 98, 0.87); color: rgb(0, 0, 0);font-weight: bold; font-size: 120%;">0.08</span></li>
    <li><span valign="middle"; align="center";  style="background: rgba(71, 177, 139, 0.87); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">0.06</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(64, 160, 180, 0.87); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">0.04</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(67, 105, 196, 0.75); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">0.02</span></li>
    <li><span valign="middle"; align="center"; style="background: rgba(79, 87, 183, 0.58); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">0.01</span></li>
    <li><span valign="middle"; align="center";  style="background: rgba(82, 71, 141, 0); color: rgb(255, 255, 255);font-weight: bold; font-size: 120%;">0</span></li>


  </ul>
</div>
</div>
<script>
    let titles = """+ f"""{[e for e in od]}"""+""";
    let currentIndex = 1;
    let text = document.getElementById('txt');
    
   
   
    setTimeout(function () {
 

    setInterval(() => {
       
       text.innerHTML= titles[currentIndex];   
       
       currentIndex++;
       
       if (currentIndex === 8)
        currentIndex = 0;
    
    }, 1000)
  
  }, 400)

    
    
    </script>
</body>
</html>

<style type='text/css'>
  .maplegend .legend-title {
    text-align: left;
    margin-bottom: 5px;
    font-weight: bold;
    font-size: 100%;
    }
  .maplegend .legend-scale ul {
    margin: 0;
    margin-bottom: 5px;
    padding: 0;
    float: right;
    list-style: none;
    }
  .maplegend .legend-scale ul li {
    font-size: 80%;
    list-style: none;
    margin-left: 0;
    line-height: 18px;
    margin-bottom: 2px;
    }
  .maplegend ul.legend-labels li span {
    display: block;
    float: left;
    height: 16px;
    width: 30px;
    margin-right: 5px;
    margin-left: 0;
    border: 1px solid #999;
    }
  .maplegend .legend-source {
    font-size: 80%;
    color: #777;
    clear: both;
    }
  .maplegend a {
    color: #777;
    }
/*////*/


    body{
                background: #000;
            }

        /*h1{ 
            text-align: center;
            font-size: 24pt;
            background-color: transparent;
            color: white;
            
            }*/
        
</style>
    {% endmacro %}"""

    macro = MacroElement()
    macro._template = Template(template)

    m.get_root().add_child(macro)

    # folium.TileLayer(_url, attr='Tiles &copy; Esri &mdash; Copyright: &copy;2012 DeLorme', name='DeLorme').add_to(m)m.add_child(colormap)
    add_gif(m, 'MRMS', f'{save_path}/img/mrms.gif', [[lat_min, lon_min], [lat_max, lon_max]], True)



    from folium.plugins import MiniMap
    minimap = MiniMap(toggle_display=True,position="bottomleft")
    m.add_child(minimap)

    from folium.plugins import MeasureControl
    m.add_child(MeasureControl())

    # os.system(f'rm *.grib2')
    # os.system(f'rm *.nc')
    print('saving map...')
    #m.save("MRMS.html")

    from git import Repo
    full_local_path = f"{save_path}/blackhawk707070.github.io/"
    username = "blackhawk707070"
    password = "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"
    remote =f"https://{username}:{password}@github.com/blackhawk707070/blackhawk707070.github.io.git"
    Repo.clone_from(remote, full_local_path)
    repo = Repo(full_local_path)
    m.save(f"{full_local_path}index.html")
    repo.git.add(f"{full_local_path}index.html")
    repo.index.commit(f"{hour}:{minute} {month}/{day}/{year}")
    repo = Repo(full_local_path)
    origin = repo.remote(name="origin")
    origin.push()
    subprocess.check_call(['rm','-rf' ,'mrms.grib2', 'mrms.nc', 'blackhawk707070.github.io'])
    print('done !')
    


def run(save_path):
    main(save_path)


if __name__ == "__main__":
    typer.run(run)
