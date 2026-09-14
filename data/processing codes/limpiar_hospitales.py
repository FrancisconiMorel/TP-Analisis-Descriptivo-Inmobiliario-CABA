import pandas as pd
from pyproj import Transformer, CRS

# 1. Cargar el CSV
df = pd.read_csv("data/raw/hospitales.csv")

# 2. Extraer x e y del formato "POINT (x y)"
coords = df["geometry"].str.extract(r"POINT \(([-\d.]+) ([-\d.]+)\)").astype(float)
x, y = coords[0], coords[1]

# 3. Definir la proyección local del GCBA ("Gauss-Krüger Buenos Aires" / "0 de Flores")
#    Nota: las coordenadas de este dataset están desplazadas respecto al origen
#    estándar documentado (x_0=100000, y_0=100000). Se calibró comparando la
#    posición calculada del Hospital Garrahan contra su ubicación real conocida,
#    lo que arrojó un offset adicional de +80000 en x y +30000 en y.
proj4_gcba = (
    "+proj=tmerc +lat_0=-34.6297166 +lon_0=-58.4627 "
    "+k=0.9999980000000001 +x_0=100000 +y_0=100000 "
    "+ellps=intl +towgs84=-148,136,90,0,0,0,0 +units=m +no_defs"
)
crs_gcba = CRS.from_proj4(proj4_gcba)
transformer = Transformer.from_crs(crs_gcba, "EPSG:4326", always_xy=True)

OFFSET_X = 80000
OFFSET_Y = 30000

lon, lat = transformer.transform((x + OFFSET_X).values, (y + OFFSET_Y).values)

# 4. Crear las columnas nuevas
df["latitud"] = lat
df["longitud"] = lon

# 5. Guardar resultado
df.to_csv("data/processed/hospitales_limpio.csv", index=False)
print(df[["nam", "dir", "latitud", "longitud"]].head())